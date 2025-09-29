# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import dataclasses
import re

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, Unpack
from typing import cast as typing_cast

import pydantic

from . import lib
from .callable_decorator import CallguardCallableDecorator
from .classmethod_decorator import CallguardClassmethodDecorator
from .defines import LOG
from .property_decorator import CallguardPropertyDecorator


if TYPE_CHECKING:
    from collections.abc import Iterable

    from .types import (
        CallguardClassOptions,
        CallguardFilterInfo,
        CallguardFilterMethod,
        CallguardGuardMethod,
        CallguardOptions,
        CallguardWrappedDecorator,
        CallguardWrappedDecoratorFactory,
    )


# MARK: Class decorator
class CallguardClassDecorator[T: object]:
    def __init__(self, **callguard_options: Unpack[CallguardClassOptions[T]]) -> None:
        self.options = callguard_options

    def __call__(self, cls: T) -> T:
        return self.guard(cls, **self.options)  # pyright: ignore[reportArgumentType, reportReturnType]

    @staticmethod
    def _individual_ignore_patterns_match(name: str, patterns: Iterable[str | re.Pattern[str]] | re.Pattern[str] | str | None) -> bool:
        if patterns is None:
            return False
        if isinstance(patterns, (str, re.Pattern)):
            return bool(re.match(patterns, name))
        return any(re.match(pattern, name) for pattern in patterns)

    @classmethod
    def _ignore_patterns_match(cls, *, name: str, guard: bool, decorate: bool, options: CallguardClassOptions[T]) -> tuple[bool, bool]:
        if cls._individual_ignore_patterns_match(name, options.get("ignore_patterns", None)):
            guard = False
            decorate = False
        else:
            if guard and cls._individual_ignore_patterns_match(name, options.get("guard_ignore_patterns", None)):
                guard = False
            if decorate and cls._individual_ignore_patterns_match(name, options.get("decorate_ignore_patterns", None)):
                decorate = False
        return (guard, decorate)

    @classmethod
    def _get_custom_decorator[**P, R](
        cls, klass: type[T], options: CallguardClassOptions[T]
    ) -> tuple[CallguardWrappedDecorator[T, P, R] | None, CallguardWrappedDecoratorFactory[T, P, R] | None]:
        # Decorator
        decorator = options.get("decorator", None)
        if decorator is None:
            decorator = typing_cast("CallguardWrappedDecorator[T, P, R] | None", getattr(klass, "__callguard_decorator__", None))
        if decorator is not None:
            if not callable(decorator):
                msg = f"Custom decorator {decorator} must be callable"
                raise ValueError(msg)

        factory = options.get("decorator_factory", None)
        if factory is None:
            factory = typing_cast("CallguardWrappedDecoratorFactory[T, P, R] | None", getattr(klass, "__callguard_decorator_factory__", None))
        if factory is not None:
            if not callable(factory):
                msg = f"Custom decorator factory {factory} must be callable"
                raise ValueError(msg)

        if decorator is not None and factory is not None:
            msg = "Cannot specify both 'decorator' and 'decorator_factory'"
            raise ValueError(msg)

        return (decorator, factory)

    @classmethod
    def _collect_pydantic_decorators(cls, klass: type[T]) -> tuple[str, ...]:
        if issubclass(klass, pydantic.BaseModel):
            infos = klass.__pydantic_decorators__
            validator_dicts = (getattr(infos, v.name) for v in dataclasses.fields(infos))
            return tuple(k for d in validator_dicts for k in d)
        else:
            return ()

    @classmethod
    def _call_individual_filter_method(cls, **info: Unpack[CallguardFilterInfo[T]]) -> bool:
        klass = info.get("klass")
        if klass is None:
            msg = "Class not found"
            raise RuntimeError(msg)
        callguard_filter_method = typing_cast("CallguardFilterMethod[T] | None", getattr(klass, "__callguard_filter__", None))
        if callguard_filter_method is not None:
            if not callable(callguard_filter_method):
                msg = f"Class {klass.__name__} has a non-callable __callguard_filter__ attribute"
                raise RuntimeError(msg)
            return callguard_filter_method(**info)
        return True

    @classmethod
    def _call_filter_method(cls, *, klass: type[T], attribute: str, value: Any, guard: bool, decorate: bool) -> tuple[bool, bool]:
        for _guard, _decorate in ((guard, False), (False, decorate)):
            if not (_guard or _decorate):
                continue

            if not cls._call_individual_filter_method(klass=klass, attribute=attribute, value=value, guard=_guard, decorate=_decorate):
                if _guard:
                    guard = False
                else:
                    decorate = False
        return (guard, decorate)

    @classmethod
    def _filter_by_name(
        cls, klass: type[T], name: str, value: Any, callguard_class_options: CallguardClassOptions[T], pydantic_decorators: tuple[str, ...]
    ) -> tuple[bool, bool]:
        if name in pydantic_decorators:
            LOG.debug(t"Callguard: Skipping {klass.__name__}.{name} as it is a pydantic decorator")
            return (False, False)

        # Parse options
        guard_private_methods: bool = bool(callguard_class_options.get("guard_private_methods", True))
        decorate_private_methods: bool = bool(callguard_class_options.get("decorate_private_methods", False))
        private_methods = guard_private_methods or decorate_private_methods

        guard_public_methods: bool = bool(callguard_class_options.get("guard_public_methods", False))
        decorate_public_methods: bool = bool(callguard_class_options.get("decorate_public_methods", False))
        public_methods = guard_public_methods or decorate_public_methods

        # Start
        guard = False
        decorate = False

        # Filter out public/dunder methods
        if name.startswith("__") and name.endswith("__"):
            pass
        elif name.startswith("_"):
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
    def _guard_attribute[_T, **P, R](  # noqa: UP049 as T is already used in the class scope
        cls, *, class_options: CallguardClassOptions[T], value: _T, **options: Unpack[CallguardOptions[_T, ..., Any]]
    ) -> _T | None:
        guard_skip_classmethods: bool = bool(class_options.get("guard_skip_classmethods", False))
        decorate_skip_classmethods: bool = bool(class_options.get("decorate_skip_classmethods", True))

        guard_skip_instancemethods: bool = bool(class_options.get("guard_skip_instancemethods", False))
        decorate_skip_instancemethods: bool = bool(class_options.get("decorate_skip_instancemethods", False))

        guard_skip_properties: bool = bool(class_options.get("guard_skip_properties", False))
        decorate_skip_properties: bool = bool(class_options.get("decorate_skip_properties", False))

        guard_fn: CallguardGuardMethod[_T, P, R] | None = None

        guard = True
        decorate = True

        if isinstance(value, pydantic.fields.ModelPrivateAttr):
            guard = not guard_skip_properties
            decorate = not decorate_skip_properties
            LOG.info("YAY")
        if isinstance(value, staticmethod):
            return value  # Static methods can't be guarded, as they have no self/cls
        elif isinstance(value, property):
            guard = not guard_skip_properties
            decorate = not decorate_skip_properties
            guard_fn = typing_cast("CallguardGuardMethod[_T, P, R]", CallguardPropertyDecorator.guard)
        elif isinstance(value, classmethod):
            guard = not guard_skip_classmethods
            decorate = not decorate_skip_classmethods
            guard_fn = typing_cast("CallguardGuardMethod[_T, P, R]", CallguardClassmethodDecorator.guard)
        elif isinstance(value, type):
            return value  # Classes are not recursively guarded
        elif callable(value):
            guard = not guard_skip_instancemethods
            decorate = not decorate_skip_instancemethods
            guard_fn = typing_cast("CallguardGuardMethod[_T, P, R]", CallguardCallableDecorator.guard)
        else:
            LOG.debug(t"Skipping non-callable, non-property attribute {options.get('method_name', '<unknown>')} of type {type(value)}")
            return value

        if guard_fn is None:
            msg = f"Cannot guard attribute of type {type(value)}"
            raise ValueError(msg)

        if not guard:
            options.update({"guard": False})
        if not decorate:
            options.update(
                {
                    "decorator": None,
                    "decorator_factory": None,
                }
            )

        return guard_fn(value, **options)

    @classmethod
    def _filter_attribute_name(cls, name: str, *, private: bool, public: bool) -> bool:
        if name.startswith("__") and name.endswith("__"):
            return False
        elif name.startswith("_"):
            return private
        else:
            return public

    @staticmethod
    def _getattribute(klass: type[T], obj: T, name: str) -> Any:
        return super(klass, obj).__getattribute__(name)

    @classmethod
    def _mark_callguarded(cls, klass: type[T]) -> None:
        setattr(klass, f"_{klass.__name__}__callguarded__", True)

        if not getattr(klass, "__callguarded__", False):
            LOG.debug(t"Callguard: Marking class {klass.__name__} as callguarded")
            setattr(klass, "__callguarded__", True)

            # Inject __init_subclass__ to auto-guard subclasses, if the inheritance chain does not already have it
            original_init_subclass = klass.__dict__.get("__init_subclass__", None)
            if original_init_subclass is not None and not isinstance(original_init_subclass, classmethod):
                msg = f"Class {klass.__name__} has a non-classmethod __init_subclass__, cannot wrap it"
                raise TypeError(msg)

            @classmethod
            def __get_callguard_class_options__(subcls: type[Self]) -> CallguardClassOptions[T] | None:  # noqa: N807 as this is a custom special method
                options = getattr(subcls, "__callguard_class_options__", None)
                if options is None:
                    msg = f"Could not find a valid '__callguard_class_options__' attribute in {subcls.__name__}"
                    raise ValueError(msg)

                for mro in subcls.__mro__:
                    if mro is subcls:
                        continue
                    if hasattr(mro, "__get_callguard_class_options__"):
                        break
                else:
                    return options

                LOG.error(t"Found {subcls.__name__} superclass {mro.__name__} with __get_callguard_class_options__")
                options_super = mro.__get_callguard_class_options__()
                if options_super is None:
                    return options

                result = options_super.copy()
                result.update(options)
                return result

            setattr(klass, "__get_callguard_class_options__", __get_callguard_class_options__)

            @classmethod
            def init_subclass_wrapper(subcls: type[Self], *args, **kwargs) -> None:
                LOG.debug(t"__init_subclass__: {cls.__name__} -> {klass.__name__} -> {subcls.__name__}")

                if original_init_subclass is not None:
                    original_init_subclass.__func__(subcls, *args, **kwargs)
                else:
                    super(klass, subcls).__init_subclass__(*args, **kwargs)

                options = subcls.__get_callguard_class_options__()  # pyright: ignore[reportAttributeAccessIssue] as we know this method exists
                CallguardClassDecorator.guard(subcls, **options)

            setattr(klass, "__init_subclass__", init_subclass_wrapper)

    @classmethod
    def guard(cls, klass: type[T], **callguard_class_options: Unpack[CallguardClassOptions[T]]) -> type[T]:
        LOG.error(t"Callguard: Guarding class {klass.__name__}")

        # Check if we should proceed
        if not lib.callguard_enabled(klass, skip_if_already_guarded=False):
            return klass

        setattr(klass, "__callguard_class_options__", callguard_class_options)

        if getattr(klass, f"_{klass.__name__}__callguarded__", False):
            # Already callguarded
            LOG.debug(t"Callguard: Class {klass.__name__} is already callguarded, skipping")
            return klass

        # Decoration
        (decorator, decorator_factory) = cls._get_custom_decorator(klass, callguard_class_options)

        # If class is a pydantic model, prepare the list of decorators
        pydantic_decorators = cls._collect_pydantic_decorators(klass)

        # Patch methods and properties in-place
        modifications = {}

        d = klass.__dict__
        if not isinstance(d, Mapping):
            msg = f"klass must have a __dict__ Mapping, got {type(d)} instead"
            raise TypeError(msg)

        for name, value in d.items():
            LOG.debug(t"Callguard: Inspecting {klass.__name__}.{name} of type {type(value)}")

            # Filter by name
            (guard, decorate) = cls._filter_by_name(
                klass=klass, name=name, value=value, callguard_class_options=callguard_class_options, pydantic_decorators=pydantic_decorators
            )

            # Skip if neither guarding nor decorating
            if not guard and not decorate:
                continue

            # Sanity check
            if decorate and (decorator is None and decorator_factory is None):
                msg = "Cannot decorate methods without a custom decorator or factory"
                raise ValueError(msg)

            # Wrap the method/property
            modification = cls._guard_attribute(
                class_options=callguard_class_options,
                value=value,
                check_module=name.startswith(("__", f"_{klass.__name__}__")),
                allow_same_class=bool(callguard_class_options.get("allow_same_class", True)),
                allow_same_module=bool(callguard_class_options.get("allow_same_module", True)),
                method_name=name,
                guard=guard,
                decorator=decorator if decorate else None,
                decorator_factory=decorator_factory if decorate else None,
            )
            if modification is not value:
                modifications[name] = modification

        # Apply modifications
        for name, value in modifications.items():
            LOG.info(t"Callguard: Patching {klass.__name__}.{name}")
            setattr(klass, name, value)

        # Mark class as callguarded
        cls._mark_callguarded(klass)

        # Done
        return klass


def callguard_class[T: object](**callguard_options: Unpack[CallguardClassOptions[T]]) -> CallguardClassDecorator[T]:
    return CallguardClassDecorator(**callguard_options)
