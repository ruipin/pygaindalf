# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging
import inspect
import functools
import dataclasses
import re

from types import FrameType
from typing import (Any, Iterable, ParamSpec, Concatenate, TypedDict, NotRequired, Unpack, overload, Literal, Annotated, Protocol, runtime_checkable, Mapping,
    cast as typing_cast,
)
from collections.abc import Callable
import pydantic
from typing_extensions import runtime
from pydantic import BaseModel

from ..logging import getLogger

from .wrappers import WrapperDecorator


# MARK: Configuration
CALLGUARD_ENABLED = True # Global enable/disable switch
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
type CallguardWrapped[T : object, **P, R] = Callable[Concatenate[T,P], R]
type CallguardWrappedDecorator[T : object, **P, R] = Callable[[CallguardWrapped[T,P,R]], CallguardWrapped[T,P,R]]

class CallguardWrappedDecoratorFactory[T : object, **P, R](Protocol):
    @classmethod
    def __call__(cls, **options : 'Unpack[CallguardOptions]') -> CallguardWrappedDecorator[T,P,R]: ...

class CallguardFilterInfo[T : object](TypedDict):
    klass     : type[T]
    attribute : str
    value     : Any
    guard     : bool
    decorate  : bool

class CallguardFilterMethod[T : object](Protocol):
    @classmethod
    def __call__(cls, **info : Unpack[CallguardFilterInfo[T]]) -> bool: ...

@dataclasses.dataclass(slots=True, frozen=True)
class CallguardHandlerInfo[T : object, **P, R]:
    method_name : str
    check_module : bool
    check_self : bool
    allow_same_module : bool
    caller_frame : FrameType
    callee_frame : FrameType
    caller_self : object
    callee_self : object
    caller_module : str
    callee_module : str
    default_checker : 'Callable[[CallguardHandlerInfo], bool]'
    default_handler : 'Callable[Concatenate[T, Callable[Concatenate[T,P], R], CallguardHandlerInfo, P], R]'


class CallguardOptions[T : object, **P, R](TypedDict):
    method_name       : NotRequired[str]
    check_module      : NotRequired[bool]
    allow_same_module : NotRequired[bool]
    guard             : NotRequired[bool]
    decorator         : NotRequired[CallguardWrappedDecorator[T,P,R] | None]
    decorator_factory : NotRequired[CallguardWrappedDecoratorFactory[T,P,R] | None]

class CallguardGuardMethod[T : object, **P, R](Protocol):
    @classmethod
    def __call__(cls, method : T, **options : Unpack[CallguardOptions[T,P,R]]) -> T: ...


class CallguardClassOptions[T : object, **P, R](TypedDict):
    force                         : NotRequired[bool]
    ignore_patterns               : NotRequired[Iterable[str | re.Pattern[str]]]
    guard_private_methods         : NotRequired[bool]
    guard_public_methods          : NotRequired[bool]
    guard_dunder_methods          : NotRequired[bool]
    guard_skip_classmethods       : NotRequired[bool]
    guard_skip_instancemethods    : NotRequired[bool]
    guard_skip_properties         : NotRequired[bool]
    guard_ignore_patterns         : NotRequired[Iterable[str | re.Pattern[str]]]
    decorate_private_methods      : NotRequired[bool]
    decorate_public_methods       : NotRequired[bool]
    decorate_dunder_methods       : NotRequired[bool]
    decorate_skip_classmethods    : NotRequired[bool]
    decorate_skip_instancemethods : NotRequired[bool]
    decorate_skip_properties      : NotRequired[bool]
    decorate_ignore_patterns      : NotRequired[Iterable[str | re.Pattern[str]]]
    decorator                     : NotRequired[CallguardWrappedDecorator[T,P,R]]
    decorator_factory             : NotRequired[CallguardWrappedDecoratorFactory[T,P,R]]
    allow_same_module             : NotRequired[bool]


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

    if info.check_module:
        if info.caller_module != info.callee_module:
            LOG.error(f"Module mismatch: caller {info.caller_module}, callee {info.callee_module}")
            return False

    if info.allow_same_module:
        if info.caller_module == info.callee_module:
            return True

    if info.check_self:
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

    def __init__(self, **options : Unpack[CallguardOptions[T,P,R]]):
        self.options = options

    def __call__(self, method : CallguardWrapped[T,P,R]) -> CallguardWrapped[T,P,R]:
        return self.guard(method, **self.options)

    @staticmethod
    def default_handler(obj : T, method : CallguardWrapped[T,P,R], info : CallguardHandlerInfo[T,P,R], *args : P.args, **kwargs : P.kwargs) -> R:
        if not info.default_checker(info):
            raise RuntimeError(f"Callguard: Unauthorized call to {info.callee_module}.{info.method_name} of instance {info.callee_self}, from {info.caller_module}.{info.caller_frame.f_code.co_qualname} of instance {info.caller_self}")
        return method(obj, *args, **kwargs)

    @staticmethod
    def guard(method : CallguardWrapped[T,P,R], **callguard_options : Unpack[CallguardOptions[T,P,R]]) -> CallguardWrapped[T,P,R]:
        if not _callguard_enabled(method):
            return method

        decorator = callguard_options.get('decorator', None)
        decorator_factory = callguard_options.get('decorator_factory', None)

        if decorator_factory is not None:
            if decorator is not None:
                raise ValueError("Cannot specify both 'decorator' and 'decorator_factory'")
            decorator = decorator_factory(**callguard_options)

        if decorator is not None:
            method = decorator(method)


        check_module = callguard_options.get('check_module', False)
        allow_same_module = callguard_options.get('allow_same_module', False)
        method_name = callguard_options.get('method_name', method.__name__)
        guard = callguard_options.get('guard', True)

        if guard:
            wrapped = method
            @functools.wraps(wrapped)
            def _wrapper(self : T, *args : P.args, **kwargs : P.kwargs) -> R:
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
                            allow_same_module=allow_same_module,
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
                                return self.__callguard_handler__(wrapped, info, *args, **kwargs)
                            else:
                                return info.default_handler(self, wrapped, info, *args, **kwargs)
                        finally:
                            del info
                    finally:
                        del caller_frame
                finally:
                    del callee_frame
            method = _wrapper

        setattr(method, '__callguarded__', True)
        return method

def callguard_callable[T : object,**P,R](**callguard_options : Unpack[CallguardOptions[T,P,R]]) -> CallguardCallableDecorator[T,P,R]:
    return CallguardCallableDecorator(**callguard_options)


# MARK: Classmethod Decorator
type WrappedClassmethod[T : object, **P, R] = classmethod[T,P,R]

class CallguardClassmethodDecorator[T : object, **P, R]:
    def __init__(self, **options : Unpack[CallguardOptions[T,P,R]]):
        self.options = options

    def __call__(self, method : WrappedClassmethod) -> WrappedClassmethod:
        return self.guard(method, **self.options)

    @staticmethod
    def guard(method : WrappedClassmethod, **callguard_options : Unpack[CallguardOptions[T,P,R]]) -> WrappedClassmethod[T,P,R]:
        if not _callguard_enabled(method):
            return method

        callguarded = typing_cast(
            CallguardWrapped[type[T],P,R],
            CallguardCallableDecorator.guard(method.__func__, **callguard_options)
        )
        if callguarded is method.__func__:
            return method

        result = classmethod(callguarded)
        result.__doc__ = method.__doc__
        return result

def callguard_classmethod[T : object, **P, R](**callguard_options : Unpack[CallguardOptions[T,P,R]]) -> CallguardClassmethodDecorator[T,P,R]:
    return CallguardClassmethodDecorator(**callguard_options)


# MARK: Property Decorator
class CallguardPropertyDecorator[T : object, **P, R]:
    def __init__(self, **options : Unpack[CallguardOptions[T,P,R]]):
        self.options = options

    def __call__(self, prop : property) -> property:
        return self.guard(prop, **self.options)

    @staticmethod
    def guard(method : property, **callguard_options : Unpack[CallguardOptions[T,P,R]]) -> property:
        if not _callguard_enabled(method):
            return method

        getter = method.fget
        setter = method.fset
        deleter = method.fdel

        orig_name = callguard_options.get('method_name', method.__name__)

        callguard_options['method_name'] = f"{orig_name}"
        callguarded_getter  = CallguardCallableDecorator.guard(getter, **callguard_options) if getter else None

        callguard_options['method_name'] = f"{orig_name}.setter"
        callguarded_setter = CallguardCallableDecorator.guard(setter, **callguard_options) if setter else None

        callguard_options['method_name'] = f"{orig_name}.deleter"
        callguarded_deleter = CallguardCallableDecorator.guard(deleter, **callguard_options) if deleter else None

        if callguarded_getter is getter and callguarded_setter is setter and callguarded_deleter is deleter:
            return method

        return property(
            callguarded_getter,
            callguarded_setter,
            callguarded_deleter,
            method.__doc__
        )

def callguard_property[T : object, **P, R](**callguard_options : Unpack[CallguardOptions[T,P,R]]) -> CallguardPropertyDecorator[T,P,R]:
    return CallguardPropertyDecorator(**callguard_options)


# MARK: Class decorator
class CallguardClassDecorator[T : object, **P, R]:
    @runtime_checkable
    class PydanticDescriptorProtocol(Protocol):
        @property
        def decorator_info(self): ...

    def __init__(self, **callguard_options: Unpack[CallguardClassOptions[T,P,R]]):
        self.options = callguard_options

    def __call__(self, cls: T) -> T:
        return self.guard(cls, **self.options)  # type: ignore

    @staticmethod
    def _individual_ignore_patterns_match(name : str, patterns : Iterable[str | re.Pattern[str]] | re.Pattern[str] | str | None) -> bool:
        if patterns is None:
            return False
        if isinstance(patterns, (str, re.Pattern)):
            return bool(re.match(patterns, name))
        return any(re.match(pattern, name) for pattern in patterns)

    @classmethod
    def _ignore_patterns_match(cls, *, name : str, guard : bool, decorate : bool, options : CallguardClassOptions[T,P,R]) -> tuple[bool, bool]:
        if cls._individual_ignore_patterns_match(name, options.get('ignore_patterns', None)):
            guard = False
            decorate = False
        else:
            if guard and cls._individual_ignore_patterns_match(name, options.get('guard_ignore_patterns', None)):
                guard = False
            if decorate and cls._individual_ignore_patterns_match(name, options.get('decorate_ignore_patterns', None)):
                decorate = False
        return (guard, decorate)

    @classmethod
    def _get_custom_decorator(cls, klass : type[T], options : CallguardClassOptions[T,P,R]) -> tuple[CallguardWrappedDecorator[T,P,R] | None, CallguardWrappedDecoratorFactory[T,P,R] | None]:
        # Decorator
        decorator = options.get('decorator', None)
        if decorator is None:
            decorator = typing_cast(CallguardWrappedDecorator[T,P,R] | None, getattr(klass, '__callguard_decorator__', None))
        if decorator is not None:
            if not callable(decorator):
                raise ValueError(f"Custom decorator {decorator} must be callable")

        factory = options.get('decorator_factory', None)
        if factory is None:
            factory = typing_cast(CallguardWrappedDecoratorFactory[T,P,R] | None, getattr(klass, '__callguard_decorator_factory__', None))
        if factory is not None:
            if not callable(factory):
                raise ValueError(f"Custom decorator factory {factory} must be callable")

        if decorator is not None and factory is not None:
            raise ValueError("Cannot specify both 'decorator' and 'decorator_factory'")

        return (decorator, factory)

    @classmethod
    def _collect_pydantic_decorators(cls, klass : type[T], options : CallguardClassOptions[T,P,R]) -> tuple[str, ...]:
        if issubclass(klass, BaseModel):
            infos = klass.__pydantic_decorators__
            validator_dicts = (getattr(infos, v.name) for v in dataclasses.fields(infos))
            return tuple(k for d in validator_dicts for k in d.keys())
        else:
            return ()

    @classmethod
    def _call_individual_filter_method(cls, **info : Unpack[CallguardFilterInfo[T]]) -> bool:
        klass = info.get('klass', None)
        if klass is None:
            raise RuntimeError("Class not found")
        callguard_filter_method = typing_cast(CallguardFilterMethod[T] | None, getattr(klass, '__callguard_filter__', None))
        if callguard_filter_method is not None:
            if not callable(callguard_filter_method):
                raise RuntimeError(f"Class {klass.__name__} has a non-callable __callguard_filter__ attribute")
            return callguard_filter_method(**info)
        return True

    @classmethod
    def _call_filter_method(cls, *, klass : type[T], attribute : str, value : Any, guard : bool, decorate : bool) -> tuple[bool, bool]:
        for _guard, _decorate in ((guard, False), (False, decorate)):
            if not (_guard or _decorate):
                continue

            if not cls._call_individual_filter_method(
                klass=klass,
                attribute=attribute,
                value=value,
                guard=_guard,
                decorate=_decorate
            ):
                if _guard:
                    guard = False
                else:
                    decorate = False
        return (guard, decorate)

    @classmethod
    def _guard_attribute[_T](cls, *, class_options : CallguardClassOptions[T,P,R], value : _T, **options : Unpack[CallguardOptions[_T,P,R]]) -> _T | None:
        guard_skip_classmethods      : bool = bool(class_options.get('guard_skip_classmethods'   , False))
        decorate_skip_classmethods   : bool = bool(class_options.get('decorate_skip_classmethods', True ))

        guard_skip_instancemethods   : bool = bool(class_options.get('guard_skip_instancemethods'   , False))
        decorate_skip_instancemethods: bool = bool(class_options.get('decorate_skip_instancemethods', False))

        guard_skip_properties        : bool = bool(class_options.get('guard_skip_properties'   , False))
        decorate_skip_properties     : bool = bool(class_options.get('decorate_skip_properties', False))

        guard_fn : CallguardGuardMethod[_T,P,R] | None = None

        guard = True
        decorate = True

        if isinstance(value, staticmethod):
            return value # Static methods can't be guarded, as they have no self/cls
        elif isinstance(value, property):
            guard = not guard_skip_properties
            decorate = not decorate_skip_properties
            guard_fn = typing_cast(CallguardGuardMethod[_T,P,R], CallguardPropertyDecorator.guard)
        elif isinstance(value, classmethod):
            guard = not guard_skip_classmethods
            decorate = not decorate_skip_classmethods
            guard_fn = typing_cast(CallguardGuardMethod[_T,P,R], CallguardClassmethodDecorator.guard)
        elif isinstance(value, type):
            return value # Classes are not recursively guarded
        elif callable(value):
            guard = not guard_skip_instancemethods
            decorate = not decorate_skip_instancemethods
            guard_fn = typing_cast(CallguardGuardMethod[_T,P,R], CallguardCallableDecorator.guard)
        else:
            LOG.debug(f"Skipping non-callable, non-property attribute {options.get('method_name', '<unknown>')} of type {type(value)}")
            return value

        if guard_fn is None:
            raise ValueError(f"Cannot guard attribute of type {type(value)}")

        if not guard:
            options.update({'guard': False})
        if not decorate:
            options.update({
                'decorator': None,
                'decorator_factory': None,
            })

        return guard_fn(value, **options)

    @classmethod
    def guard(cls, klass: type[T], **callguard_class_options: Unpack[CallguardClassOptions[T,P,R]]) -> type[T]:
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

        # Decoration
        (decorator, decorator_factory) = cls._get_custom_decorator(klass, callguard_class_options)

        # Default values
        guard_private_methods    : bool = bool(callguard_class_options.get('guard_private_methods'   , True ))
        decorate_private_methods : bool = bool(callguard_class_options.get('decorate_private_methods', False))
        private_methods = guard_private_methods or decorate_private_methods

        guard_public_methods     : bool = bool(callguard_class_options.get('guard_public_methods'   , False))
        decorate_public_methods  : bool = bool(callguard_class_options.get('decorate_public_methods', False))
        public_methods = guard_public_methods or decorate_public_methods

        guard_dunder_methods     : bool = bool(callguard_class_options.get('guard_dunder_methods'   , False))
        decorate_dunder_methods  : bool = bool(callguard_class_options.get('decorate_dunder_methods', False))
        dunder_methods = guard_dunder_methods or decorate_dunder_methods

        if (decorate_private_methods or decorate_public_methods or decorate_dunder_methods) and (not decorator and not decorator_factory):
            raise ValueError("Cannot decorate methods without a custom decorator or factory")

        allow_same_module : bool = bool(callguard_class_options.get('allow_same_module', False))

        # If class is a pydantic model, prepare the list of decorators
        pydantic_decorators = cls._collect_pydantic_decorators(klass, callguard_class_options)

        # Patch methods and properties in-place
        modifications = {}

        d = klass.__dict__
        if not isinstance(d, Mapping):
            raise ValueError(f"klass must have a __dict__ Mapping, got {type(d)} instead")

        for name, value in d.items():
            guard = False
            decorate = False

            # Filter out public/dunder methods
            if name.startswith('_'):
                if name.startswith('__') and name.endswith('__'):
                    if not dunder_methods:
                        continue
                    guard = guard_dunder_methods
                    decorate = decorate_dunder_methods
                elif not private_methods:
                    continue
                guard = guard_private_methods
                decorate = decorate_private_methods
            else:
                if not public_methods:
                    continue
                guard = guard_public_methods
                decorate = decorate_public_methods

            # Skip pydantic decorators
            if name in pydantic_decorators:
                LOG.debug(f"Callguard: Skipping {klass.__name__}.{name} as it is a pydantic decorator")
                continue

            # Filter out ignored patterns
            if guard or decorate:
                (guard, decorate) = cls._ignore_patterns_match(name=name, decorate=decorate, guard=guard, options=callguard_class_options)
            # Call custom filter method, if defined
            if guard or decorate:
                (guard, decorate) = cls._call_filter_method(klass=klass, attribute=name, value=value, guard=guard, decorate=decorate)
            # Skip if neither guarding nor decorating
            if not guard and not decorate:
                continue

            # Sanity check
            if decorate and (decorator is None and decorator_factory is None):
                raise ValueError("Cannot decorate methods without a custom decorator or factory")

            # Wrap the method/property
            modification = cls._guard_attribute(
                class_options= callguard_class_options,
                value= value,
                check_module= name.startswith('__') or name.startswith(f"_{klass.__name__}__"),
                allow_same_module= allow_same_module,
                method_name= name,
                guard= guard,
                decorator= decorator if decorate else None,
                decorator_factory= decorator_factory if decorate else None,
            )
            if modification is not value:
                modifications[name] = modification

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

def callguard_class[T : object, **P, R](**callguard_options : Unpack[CallguardClassOptions[T,P,R]]) -> CallguardClassDecorator[T,P,R]:
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