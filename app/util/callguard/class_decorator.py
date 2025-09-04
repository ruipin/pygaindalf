# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


import pydantic

from typing import Unpack, runtime_checkable, Protocol, cast as typing_cast, overload
from collections.abc import Mapping

from .defines import *
from .types import *
from .lib import *
from .callable_decorator import CallguardCallableDecorator
from .property_decorator import CallguardPropertyDecorator
from .classmethod_decorator import CallguardClassmethodDecorator


# MARK: Class decorator
class CallguardClassDecorator[T : object]:
    @runtime_checkable
    class PydanticDescriptorProtocol(Protocol):
        @property
        def decorator_info(self): ...

    def __init__(self, **callguard_options: Unpack[CallguardClassOptions[T]]):
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
    def _ignore_patterns_match(cls, *, name : str, guard : bool, decorate : bool, options : CallguardClassOptions[T]) -> tuple[bool, bool]:
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
    def _get_custom_decorator[**P,R](cls, klass : type[T], options : CallguardClassOptions[T]) -> tuple[CallguardWrappedDecorator[T,P,R] | None, CallguardWrappedDecoratorFactory[T,P,R] | None]:
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
    def _collect_pydantic_decorators(cls, klass : type[T], options : CallguardClassOptions[T]) -> tuple[str, ...]:
        if issubclass(klass, pydantic.BaseModel):
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
    def _filter_by_name(cls, klass : type[T], name : str, value : Any, callguard_class_options : CallguardClassOptions[T], pydantic_decorators : tuple[str, ...]) -> tuple[bool, bool]:
        if name in pydantic_decorators:
            LOG.debug(f"Callguard: Skipping {klass.__name__}.{name} as it is a pydantic decorator")
            return (False, False)

        # Parse options
        guard_private_methods    : bool = bool(callguard_class_options.get('guard_private_methods'   , True ))
        decorate_private_methods : bool = bool(callguard_class_options.get('decorate_private_methods', False))
        private_methods = guard_private_methods or decorate_private_methods

        guard_public_methods     : bool = bool(callguard_class_options.get('guard_public_methods'   , False))
        decorate_public_methods  : bool = bool(callguard_class_options.get('decorate_public_methods', False))
        public_methods = guard_public_methods or decorate_public_methods

        # Start
        guard = False
        decorate = False

        # Filter out public/dunder methods
        if name.startswith('__') and name.endswith('__'):
            pass
        elif name.startswith('_'):
            if private_methods:
                guard = guard_private_methods
                decorate = decorate_private_methods
        else:
            if public_methods:
                guard = guard_public_methods
                decorate = decorate_public_methods

        # Filter out ignored patterns
        if guard or decorate:
            (guard, decorate) = cls._ignore_patterns_match(name=name, decorate=decorate, guard=guard, options=callguard_class_options)

        # Call custom filter method, if defined
        if guard or decorate:
            (guard, decorate) = cls._call_filter_method(klass=klass, attribute=name, value=value, guard=guard, decorate=decorate)

        # Done
        return (guard, decorate)

    @classmethod
    def _guard_attribute[_T, **P, R](cls, *, class_options : CallguardClassOptions[T], value : _T, **options : Unpack[CallguardOptions[_T,...,Any]]) -> _T | None:
        guard_skip_classmethods      : bool = bool(class_options.get('guard_skip_classmethods'   , False))
        decorate_skip_classmethods   : bool = bool(class_options.get('decorate_skip_classmethods', True ))

        guard_skip_instancemethods   : bool = bool(class_options.get('guard_skip_instancemethods'   , False))
        decorate_skip_instancemethods: bool = bool(class_options.get('decorate_skip_instancemethods', False))

        guard_skip_properties        : bool = bool(class_options.get('guard_skip_properties'   , False))
        decorate_skip_properties     : bool = bool(class_options.get('decorate_skip_properties', False))

        guard_fn : CallguardGuardMethod[_T,P,R] | None = None

        guard = True
        decorate = True

        if isinstance(value, pydantic.fields.ModelPrivateAttr):
            guard = not guard_skip_properties
            decorate = not decorate_skip_properties
            LOG.info("YAY")
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
    def _filter_attribute_name(cls, name : str, private : bool, public : bool) -> bool:
        if name.startswith('__') and name.endswith('__'):
            return False
        elif name.startswith('_'):
            return private
        else:
            return public

    @staticmethod
    def _getattribute(klass : type[T], obj : T, name : str) -> Any:
        return super(klass, obj).__getattribute__(name)

    @classmethod
    def _mark_callguarded(cls, klass : type[T], callguard_class_options : CallguardClassOptions[T]) -> None:
        setattr(klass, f'_{klass.__name__}__callguarded__', True)

        if not getattr(klass, '__callguarded__', False):
            LOG.debug(f"Callguard: Marking class {klass.__name__} as callguarded")
            setattr(klass, '__callguarded__', True)

            # Inject __init_subclass__ to auto-guard subclasses, if the inheritance chain does not already have it
            original_init_subclass = klass.__dict__.get('__init_subclass__', None)
            if original_init_subclass is not None and not isinstance(original_init_subclass, classmethod):
                raise TypeError(f"Class {klass.__name__} has a non-classmethod __init_subclass__, cannot wrap it")

            @classmethod
            def init_subclass_wrapper(subcls):
                LOG.error(f"__init_subclass__: {cls.__name__} -> {klass.__name__} -> {subcls.__name__}")

                if original_init_subclass is not None:
                    original_init_subclass.__func__(subcls)
                else:
                    super(klass, subcls).__init_subclass__()

                options = getattr(subcls, '__callguard_class_options__', None)
                if options is None:
                    raise ValueError(f"Could not find a valid '__callguard_class_options__' attribute in {subcls.__name__}")
                LOG.error(options)

                CallguardClassDecorator.guard(subcls, **options)

            setattr(klass, '__init_subclass__', init_subclass_wrapper)

    @classmethod
    def guard(cls, klass: type[T], **callguard_class_options: Unpack[CallguardClassOptions[T]]) -> type[T]:
        LOG.debug(f"Callguard: Guarding class {klass.__name__}")

        # Check if we should proceed
        if not callguard_enabled(klass, skip_if_already_guarded=False):
            return klass

        setattr(klass, '__callguard_class_options__', callguard_class_options)

        if getattr(klass, f'_{klass.__name__}__callguarded__', False):
            # Already callguarded
            LOG.debug(f"Callguard: Class {klass.__name__} is already callguarded, skipping")
            return klass

        # Decoration
        (decorator, decorator_factory) = cls._get_custom_decorator(klass, callguard_class_options)

        # If class is a pydantic model, prepare the list of decorators
        pydantic_decorators = cls._collect_pydantic_decorators(klass, callguard_class_options)

        # Patch methods and properties in-place
        modifications = {}

        d = klass.__dict__
        if not isinstance(d, Mapping):
            raise ValueError(f"klass must have a __dict__ Mapping, got {type(d)} instead")

        for name, value in d.items():
            LOG.debug(f"Callguard: Inspecting {klass.__name__}.{name} of type {type(value)}")

            # Filter by name
            (guard, decorate) = cls._filter_by_name(
                klass=klass,
                name=name,
                value=value,
                callguard_class_options=callguard_class_options,
                pydantic_decorators=pydantic_decorators
            )

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
                allow_same_module= bool(callguard_class_options.get('allow_same_module', False)),
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
        cls._mark_callguarded(klass, callguard_class_options)

        # Done
        return klass

def callguard_class[T : object](**callguard_options : Unpack[CallguardClassOptions[T]]) -> CallguardClassDecorator[T]:
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