# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging
import inspect
import functools
import dataclasses
import re

from types import FrameType
from typing import (Any, Iterable, ParamSpec, Concatenate, TypedDict, Unpack, overload, Literal, Annotated, Protocol, runtime_checkable, Mapping,
    cast as typing_cast,
)
from collections.abc import Callable
import pydantic
from typing_extensions import runtime
from pydantic import BaseModel

from ..logging import getLogger


# MARK: Configuration
CALLGUARD_ENABLED = True # Global enable/disable switch
CALLGUARD_COMPARE_MODULE = True # Whether to compare caller and callee modules
CALLGUARD_COMPARE_SELF = True # Whether to compare 'self' or 'cls' instances (if False, will skip self/cls comparison)
CALLGUARD_SELF_IS_FIRST_ARGUMENT = True # Whether to assume the first argument is 'self' or 'cls' (if False, will use introspection to find the first argument)
CALLGUARD_STRICT_SELF = True # Whether to enforce that the first argument is named 'self' or 'cls'

LOG = getLogger(__name__)
LOG.disabled = True


# MARK: Frame inspection utilities
def get_execution_frame(*, frames_up : int = 0) -> FrameType:
    # WARNING: It is important to 'del frame' once you are done with the frame!

    if frames_up < 0:
        raise ValueError("frames_up must be non-negative")

    n_frames = frames_up

    frame = inspect.currentframe()
    if frame is None:
        raise RuntimeError("No current frame available")

    try:
        while True:
            # Get the next frame up the stack
            next_frame = frame.f_back
            if next_frame is None:
                raise RuntimeError("No caller frame available")
            n_frames -= 1

            del frame
            frame = next_frame
            if n_frames <= 0:
                return frame
    except:
        del frame
        raise

def get_execution_frame_module(frame : FrameType) -> str | None:
    return frame.f_globals.get("__name__", None)

def get_execution_frame_self_varname(frame : FrameType) -> str | Iterable[str] | None:
    if not CALLGUARD_SELF_IS_FIRST_ARGUMENT:
        return ('self', 'cls')

    # Get the name of the first argument of the function/method in this frame
    code = frame.f_code
    if code.co_argcount <= 0:
        return None
    result = code.co_varnames[0]
    if CALLGUARD_STRICT_SELF:
        if result not in ('self', 'cls'):
            return None

    return result

def get_execution_frame_self(frame : FrameType) -> object | None:
    self_varnames = get_execution_frame_self_varname(frame)
    if self_varnames is None:
        return None
    if isinstance(self_varnames, str):
        self_varnames = (self_varnames,)

    for self_varname in self_varnames:
        result = frame.f_locals.get(self_varname, None)
        if result is not None:
            return result
    return None


# MARK: Option types
type CallguardWrapped[T,**P, R] = Callable[Concatenate[T,P], R]

@dataclasses.dataclass(slots=True, frozen=True)
class CallguardHandlerInfo[T : object, **P, R]:
    method_name : str
    check_module : bool
    check_self : bool
    caller_frame : FrameType
    callee_frame : FrameType
    caller_self : object
    callee_self : object
    caller_module : str
    callee_module : str
    default_checker : 'Callable[[CallguardHandlerInfo], bool]'
    default_handler : 'Callable[Concatenate[T, Callable[Concatenate[T,P], R], CallguardHandlerInfo, P], R]'

class CallguardOptions(TypedDict, total=False):
    method_name : str
    check_module : bool

class CallguardClassOptions(TypedDict, total=False):
    force : bool
    private_methods : bool
    public_methods : bool
    dunder_methods : bool
    pydantic_decorators : bool
    ignore_patterns : Iterable[str | re.Pattern[str]]


def _callguard_enabled(obj : Any = None) -> bool:
    result = CALLGUARD_ENABLED and not getattr(obj, '__callguard_disabled__', False) and not getattr(obj, '__callguarded__', False)
    if not result:
        LOG.debug(f"Callguard: Object {obj.__name__} is not callguard-enabled, skipping")
    return result


# MARK: Method decorator
def default_callguard_checker[T : object, **P, R](info : CallguardHandlerInfo[T,P,R]) -> bool:
    if LOG.isEnabledFor(logging.DEBUG):
        LOG.debug(f"Caller frame: {info.caller_frame.f_code.co_name} in {info.caller_module}")

        callee_name = info.callee_frame.f_locals.get('method_name', info.callee_frame.f_code.co_name)
        LOG.debug(f"Callee frame: {callee_name} in {info.callee_module}")

    if CALLGUARD_COMPARE_MODULE and info.check_module:
        if info.caller_module != info.callee_module:
            LOG.error(f"Module mismatch: caller {info.caller_module}, callee {info.callee_module}")
            return False

    if CALLGUARD_COMPARE_SELF and info.check_self:
        if info.caller_self is not info.callee_self:
            if (
                (not isinstance(info.callee_self, type) or not isinstance(info.caller_self, info.callee_self)) and
                (not isinstance(info.caller_self, type) or not isinstance(info.callee_self, info.caller_self))
            ):
                LOG.error(f"Self mismatch: caller {info.caller_self}, callee {info.callee_self}")
                return False
    return True

class CallguardCallableDecorator[T : object, **P, R]:
    @runtime_checkable
    class CallguardHandlerProtocol(Protocol):
        def __callguard_handler__(
            self : T,
            method : CallguardWrapped[T,P,R],
            info : CallguardHandlerInfo,
            *args : P.args,
            **kwargs : P.kwargs
        ) -> R: ...

    def __init__(self, **options : Unpack[CallguardOptions]):
        self.options = options

    def __call__(self, method : CallguardWrapped[T,P,R]) -> CallguardWrapped[T,P,R]:
        return self.guard(method, **self.options)

    @staticmethod
    def default_handler(obj : T, method : CallguardWrapped[T,P,R], info : CallguardHandlerInfo[T,P,R], *args : P.args, **kwargs : P.kwargs) -> R:
        if not info.default_checker(info):
            raise RuntimeError(f"Callguard: Unauthorized call to {info.method_name} from module {info.caller_module} and caller {info.caller_self}")
        return method(obj, *args, **kwargs)

    @staticmethod
    def guard(method : CallguardWrapped[T,P,R], **callguard_options : Unpack[CallguardOptions]) -> CallguardWrapped[T,P,R]:
        if not _callguard_enabled(method):
            return method

        check_module = callguard_options.get('check_module', False)
        method_name = callguard_options.get('method_name', method.__name__)

        @functools.wraps(method)
        def _wrapper(self : T, *args : P.args, **kwargs : P.kwargs) -> Any:
            LOG.debug(f"Callguard: Guarding call to {method_name}")

            callee_frame = get_execution_frame(frames_up=1)
            if callee_frame is None:
                raise RuntimeError("No callee frame found")

            try:
                caller_frame = callee_frame.f_back
                if caller_frame is None:
                    raise RuntimeError("No caller frame found")

                try:
                    caller_module = get_execution_frame_module(caller_frame)
                    if caller_module is None:
                        raise RuntimeError("No caller module found")

                    info : CallguardHandlerInfo[T,P,R] = CallguardHandlerInfo(
                        method_name=method_name,
                        check_module=check_module,
                        check_self=True,
                        caller_frame=caller_frame,
                        callee_frame=callee_frame,
                        caller_self=get_execution_frame_self(caller_frame),
                        callee_self=self,
                        caller_module=caller_module,
                        callee_module=method.__module__,
                        default_checker=default_callguard_checker,
                        default_handler=CallguardCallableDecorator[T,P,R].default_handler,
                    )

                    try:
                        if isinstance(self, CallguardCallableDecorator[T,P,R].CallguardHandlerProtocol):
                            return self.__callguard_handler__(method, info, *args, **kwargs)
                        else:
                            return info.default_handler(self, method, info, *args, **kwargs)
                    finally:
                        del info
                finally:
                    del caller_frame
            finally:
                del callee_frame

        setattr(_wrapper, '__callguarded__', True)
        return _wrapper

def callguard_callable(**callguard_options : Unpack[CallguardOptions]) -> CallguardCallableDecorator:
    return CallguardCallableDecorator(**callguard_options)


# MARK: Classmethod Decorator
class CallguardClassmethodDecorator[T : type, **P, R]:
    type WrappedClassmethod = classmethod[T, P, R]

    def __init__(self, **options : Unpack[CallguardOptions]):
        self.options = options

    def __call__(self, method : WrappedClassmethod) -> WrappedClassmethod:
        return self.guard(method, **self.options)

    @staticmethod
    def guard(method : WrappedClassmethod, **callguard_options : Unpack[CallguardOptions]) -> WrappedClassmethod:
        if not _callguard_enabled(method):
            return method

        callguarded = typing_cast(Callable[Concatenate[T,P],R], CallguardCallableDecorator.guard(method.__func__, **callguard_options))
        if callguarded is method.__func__:
            return method

        result = classmethod(callguarded)
        result.__doc__ = method.__doc__
        return result

def callguard_classmethod(**callguard_options : Unpack[CallguardOptions]) -> CallguardClassmethodDecorator:
    return CallguardClassmethodDecorator(**callguard_options)


# MARK: Property Decorator
class CallguardPropertyDecorator:
    def __init__(self, **options : Unpack[CallguardOptions]):
        self.options = options

    def __call__(self, prop : property) -> property:
        return self.guard(prop, **self.options)

    @staticmethod
    def guard(prop : property, **callguard_options : Unpack[CallguardOptions]) -> property:
        if not _callguard_enabled(prop):
            return prop

        getter = prop.fget
        setter = prop.fset
        deleter = prop.fdel

        orig_name = callguard_options.get('method_name', prop.__name__)

        callguard_options['method_name'] = f"{orig_name}"
        callguarded_getter  = CallguardCallableDecorator.guard(getter, **callguard_options) if getter else None

        callguard_options['method_name'] = f"{orig_name}.setter"
        callguarded_setter = CallguardCallableDecorator.guard(setter, **callguard_options) if setter else None

        callguard_options['method_name'] = f"{orig_name}.deleter"
        callguarded_deleter = CallguardCallableDecorator.guard(deleter, **callguard_options) if deleter else None

        if callguarded_getter is getter and callguarded_setter is setter and callguarded_deleter is deleter:
            return prop

        return property(
            callguarded_getter,
            callguarded_setter,
            callguarded_deleter,
            prop.__doc__
        )

def callguard_property(**callguard_options : Unpack[CallguardOptions]) -> CallguardPropertyDecorator:
    return CallguardPropertyDecorator(**callguard_options)


# MARK: Class decorator
class CallguardClassDecorator[T : type]:
    @runtime_checkable
    class PydanticDescriptorProtocol(Protocol):
        @property
        def decorator_info(self): ...

    def __init__(self, **callguard_options: Unpack[CallguardClassOptions]):
        self.options = callguard_options

    def __call__(self, cls: T) -> T:
        return self.guard(cls, **self.options)  # type: ignore

    @staticmethod
    def guard(klass: T, **callguard_class_options: Unpack[CallguardClassOptions]) -> T:
        LOG.debug(f"Callguard: Guarding class {klass.__name__}")

        # Check if we should proceed
        if not callguard_class_options.get('force', False) and not _callguard_enabled(klass):
            return klass

        if getattr(klass, f'_{klass.__name__}__callguarded__', False):
            # Already callguarded
            LOG.debug(f"Callguard: Class {klass.__name__} is already callguarded, skipping")
            return klass

        # Always force callguarding if inherited from a callguarded class
        callguard_class_options['force'] = True

        # Default values
        wrap_private_methods     : bool = callguard_class_options.get('private_methods', True )
        wrap_public_methods      : bool = callguard_class_options.get('public_methods' , False)
        wrap_dunder_methods      : bool = callguard_class_options.get('dunder_methods' , False)
        wrap_pydantic_decorators : bool = callguard_class_options.get('pydantic_decorators', False)

        # If class is a pydantic model, preparee the list of decorators
        if (not wrap_pydantic_decorators) and issubclass(klass, BaseModel):
            infos = klass.__pydantic_decorators__
            validator_dicts = (getattr(infos, v.name) for v in dataclasses.fields(infos))
            pydantic_decorators = tuple(k for d in validator_dicts for k in d.keys())
        else:
            pydantic_decorators = ()
        klass = typing_cast(T, klass) # Pyright gets confused with the issubclass call above, so we reset the klass type here

        # Patch methods and properties in-place
        modifications = {}

        d = klass.__dict__
        if not isinstance(d, Mapping):
            raise ValueError(f"klass must have a __dict__ Mapping, got {type(d)} instead")

        for name, value in d.items():
            # Filter out public/dunder methods
            if name.startswith('_'):
                if name.startswith('__') and name.endswith('__'):
                    if not wrap_dunder_methods:
                        continue
                elif not wrap_private_methods:
                    continue
            elif not wrap_public_methods:
                continue

            if name in pydantic_decorators:
                LOG.debug(f"Callguard: Skipping {klass.__name__}.{name} as it is a pydantic decorator")
                continue

            # Filter out ignored patterns
            if any(re.match(pattern, name) for pattern in callguard_class_options.get('ignore_patterns', ())):
                continue

            # Call custom filter method, if defined
            callguard_filter_method = getattr(klass, '__callguard_filter__', None)
            if callguard_filter_method is not None:
                if not callable(callguard_filter_method):
                    raise RuntimeError(f"Class {klass.__name__} has a non-callable __callguard_filter__ attribute")
                if not callguard_filter_method(name, value):
                    LOG.debug(f"Callguard: Skipping {klass.__name__}.{name} due to __callguard_filter__")
                    continue

            callguard_options : CallguardOptions = {
                'check_module': name.startswith('__') or name.startswith(f"_{klass.__name__}__"),
                'method_name': name,
            }

            # Wrap the method/property
            if isinstance(value, staticmethod):
                pass # Static methods can't be guarded, as they have no self/cls
            elif isinstance(value, property):
                modifications[name] = CallguardPropertyDecorator.guard(value, **callguard_options)
            elif isinstance(value, classmethod):
                modifications[name] = CallguardClassmethodDecorator.guard(value, **callguard_options)
            elif isinstance(value, type):
                pass # Classes are not recursively guarded
            elif callable(value):
                modifications[name] = CallguardCallableDecorator.guard(value, **callguard_options)
            else:
                LOG.debug(f"Skipping non-callable, non-property attribute {name} of type {type(value)}")

        # Apply modifications
        for name, value in modifications.items():
            LOG.debug(f"Callguard: Patching {klass.__name__}.{name}")
            setattr(klass, name, value)

        # Mark class as callguarded
        setattr(klass, f'_{klass.__name__}__callguarded__', True)
        if not getattr(klass, '__callguarded__', False):
            LOG.debug(f"Callguard: Marking class {klass.__name__} as callguarded")
            setattr(klass, '__callguarded__', True)

            # Inject __init_subclass__ to auto-guard subclasses, if the inheritance chain does not already have it
            original_init_subclass = d.get('__init_subclass__', None)
            if original_init_subclass is not None and not isinstance(original_init_subclass, classmethod):
                raise TypeError(f"Class {klass.__name__} has a non-classmethod __init_subclass__, cannot wrap it")

            @classmethod
            def init_subclass_wrapper(subcls):
                if original_init_subclass is not None:
                    original_init_subclass.__func__(subcls)
                else:
                    super(klass, subcls).__init_subclass__()
                CallguardClassDecorator.guard(subcls, **callguard_class_options)
            setattr(klass, '__init_subclass__', init_subclass_wrapper)

        # Done
        return klass

def callguard_class(**callguard_options : Unpack[CallguardClassOptions]) -> CallguardClassDecorator:
    return CallguardClassDecorator(**callguard_options)


# MARK: Generic Decorator
@overload
def callguard[T : property](obj : T, **callguard_options : Unpack[CallguardOptions]) -> T: ...

@overload
def callguard[T : classmethod](obj : T, **callguard_options : Unpack[CallguardOptions]) -> T: ...

@overload
def callguard[T : type](obj : T, **callguard_options : Unpack[CallguardClassOptions]) -> T: ...

@overload
def callguard[T : Callable](obj : T, **callguard_options : Unpack[CallguardOptions]) -> T: ...

def callguard[T](obj : T, **callguard_options) -> T:
    if isinstance(obj, staticmethod):
        raise ValueError("callguard cannot be applied to staticmethods, as they have no self/cls")
    elif isinstance(obj, property):
        return CallguardPropertyDecorator.guard(obj, **callguard_options)
    elif isinstance(obj, classmethod):
        return CallguardClassmethodDecorator.guard(obj, **callguard_options)
    elif isinstance(obj, type):
        return CallguardClassDecorator.guard(obj, **callguard_options)
    elif callable(obj):
        return CallguardCallableDecorator.guard(obj, **callguard_options)
    else:
        raise TypeError("callguard can only be applied to classes, methods, or properties")



# MARK: No callguard Decorator
def no_callguard[T : Any](obj : T) -> T:
    setattr(obj, '__callguard_disabled__', True)
    return obj


# MARK: Callguard mixin
class Callguard:
    if CALLGUARD_ENABLED:
        def __init_subclass__(cls) -> None:
            super().__init_subclass__()
            CallguardClassDecorator.guard(cls)