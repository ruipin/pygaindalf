# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools
import importlib
import inspect

from abc import ABCMeta, abstractmethod
from collections.abc import Callable
from typing import (
    Any,
    Concatenate,
    Self,
    TypeVar,
    Unpack,
)
from typing import (
    cast as typing_cast,
)

from pydantic import GetCoreSchemaHandler, ModelWrapValidatorHandler, model_validator
from pydantic_core import CoreSchema, core_schema

from app.util.mixins import LoggableHierarchicalNamedMixin

from ..util.callguard import CALLGUARD_ENABLED, CallguardOptions, CallguardWrapped, callguard_class
from ..util.config import BaseConfigModel
from ..util.config.inherit import FieldInherit
from ..util.helpers import classproperty, generics
from ..util.helpers.decimal import DecimalConfig, DecimalFactory


# MARK: Base Component Configuration
class BaseComponentConfig(BaseConfigModel, metaclass=ABCMeta):
    package: str

    decimal: DecimalConfig = FieldInherit(default_factory=DecimalConfig, description="Decimal configuration for provider")

    @model_validator(mode="wrap")
    @classmethod
    def _coerce_to_concrete_class[Child: BaseComponentConfig](cls: type[Child], data: Any, handler: ModelWrapValidatorHandler) -> Child:
        # Already instantiated
        if isinstance(data, cls):
            return data

        # Must be a dictionary
        if not isinstance(data, dict):
            msg = f"Expected a dictionary for {cls.__name__} configuration, got {type(data).__name__}."
            raise TypeError(msg)

        package = data.get("package", None)
        if package is None:
            msg = f"Missing 'package' key in {cls.__name__} configuration."
            raise ValueError(msg)

        # Get the concrete configuration class for this package
        component_cls: type = cls.get_component_class_for_package(package)

        concrete_cls = component_cls.config_class
        if concrete_cls is None:
            msg = f"Configuration class for {package} does not define 'config_class'."
            raise ImportError(msg)
        if cls is concrete_cls:
            return handler(data)
        if not issubclass(concrete_cls, cls):
            msg = f"Expected configuration class {cls.__name__}, got {concrete_cls.__name__} instead."
            raise TypeError(msg)

        return concrete_cls.model_validate(data)

    @classmethod
    def get_component_class_for_package(cls, package: str) -> type[ComponentSubclassMeta]:
        # Import the package
        root_path = cls.package_root
        rel_path = f".{package}"
        path = f"{root_path}{rel_path}"
        mod = importlib.import_module(f".{package}", root_path)

        # Get the component class
        component_cls = getattr(mod, "COMPONENT", None)
        if component_cls is None:
            msg = f"Configuration class for {package} not found in '{path}'."
            raise ImportError(msg)
        if not isinstance(component_cls, type):
            msg = f"Expected a class for {package} component, got {type(component_cls).__name__} instead."
            raise TypeError(msg)

        # Sanity check the configuration class
        config_cls = component_cls.config_class
        if config_cls is None:
            msg = f"Configuration class for {package} does not define 'config_class'."
            raise ImportError(msg)
        if not issubclass(config_cls, BaseComponentConfig):
            msg = f"Expected configuration class {cls.__name__}, got {config_cls.__name__} instead."
            raise TypeError(msg)

        # Done
        return component_cls

    @property
    def component_class(self) -> type[ComponentSubclassMeta]:
        return self.get_component_class_for_package(self.package)

    @classproperty
    @abstractmethod
    def package_root(cls) -> str:
        msg = f"{cls.__name__}.package_root() must be implemented."
        raise NotImplementedError(msg)


# MARK: Component subclassing mechanism
class ComponentSubclassMeta[C: BaseComponentConfig](LoggableHierarchicalNamedMixin, metaclass=ABCMeta):
    config: C
    config_class: type[C]

    @classmethod
    def _introspect_config_class(cls) -> type[C]:
        """Introspects the class to find the configuration class."""
        arg = generics.get_parent_argument(cls, ComponentSubclassMeta, "C")
        return typing_cast("type[C]", arg)

    @classmethod
    def __init_subclass__(cls, **kwargs) -> None:
        """Validate that all ComponentField descriptors are subclasses of their base class and create a '*_class' property for each descriptor."""
        super().__init_subclass__(**kwargs)

        # Introspect the original bases to get the configuration class
        cls.config_class = cls._introspect_config_class()
        cls.__annotations__["config_class"] = cls.config_class
        if not isinstance(cls.config_class, TypeVar):
            cls.config_class.component_class = cls  # pyright: ignore[reportAttributeAccessIssue] as we are overriding the component_class class property on purpose

        # If callguard is disabled, manually decorate all public methods with the callguard decorator
        if not CALLGUARD_ENABLED and callable(dec := getattr(cls, "__callguard_decorator__", None)):
            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                if not name.startswith("_"):
                    setattr(cls, name, dec(method, method_name=name))

    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        assert cls is source, f"Expected cls to be source, got {type(source).__name__} instead."
        return core_schema.is_instance_schema(cls)

    def __init__(self, config: C, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        if isinstance(self.config_class, TypeVar):
            msg = f"{type(self).__name__} is a generic class and must not be instantiated without providing an explicit configuration class type argument to override the TypeVar {self.config_class.__name__}."
            raise TypeError(msg)

        self.config = config


# MARK: Component entrypoint decorator
type Entrypoint[T: ComponentBase, **P, R] = Callable[Concatenate[T, P], R]


# MARK: Component Base Class
@callguard_class(
    decorate_public_methods=True,
    ignore_patterns=("inside_entrypoint"),
)
class ComponentBase[C: BaseComponentConfig](ComponentSubclassMeta[C], metaclass=ABCMeta):
    # Decimal factory for precise calculations
    decimal: DecimalFactory

    def __init__(self, config: C, *args, **kwargs) -> None:
        super().__init__(config, *args, **kwargs)
        self._inside_entrypoint = False

        self.decimal = DecimalFactory(self.config.decimal)

    @classmethod
    def component_entrypoint_decorator[**P, R](cls, entrypoint: Entrypoint[Self, P, R]) -> Entrypoint[Self, P, R]:
        entrypoint.__dict__["__component_entrypoint__"] = True
        return entrypoint

    @classmethod
    def _handle_entrypoint[**P, R](cls, entrypoint: Entrypoint[Self, P, R], self: Self, /, *args: P.args, **kwargs: P.kwargs) -> R:
        # If we are already inside an entrypoint, call it directly
        if self.inside_entrypoint:
            return entrypoint(self, *args, **kwargs)

        # Execute entrypoint
        try:
            self._inside_entrypoint = True

            self._before_entrypoint(entrypoint.__name__, *args, **kwargs)

            try:
                result = self._wrap_entrypoint(entrypoint, *args, **kwargs)
            finally:
                self._after_entrypoint(entrypoint.__name__)

        finally:
            self._inside_entrypoint = False

        return result

    @classmethod
    def __callguard_decorator__[**P, R](
        cls, method: CallguardWrapped[Self, P, R], **options: Unpack[CallguardOptions[Self, P, R]]
    ) -> CallguardWrapped[Self, P, R]:
        @functools.wraps(method)
        def _wrapper(self: Self, *args: P.args, **kwargs: P.kwargs) -> R:
            # When inside an entrypoint all calls are allowed
            if self.inside_entrypoint:
                return method(self, *args, **kwargs)

            # Fail if this is not an entrypoint
            elif not method.__dict__.get("__component_entrypoint__", False):
                msg = f"Method '{options.get('method_name', method.__name__)}' is not a component entrypoint. It must be called through a component entrypoint method."
                raise RuntimeError(msg)

            return cls._handle_entrypoint(method, self, *args, **kwargs)

        return _wrapper

    @property
    def inside_entrypoint(self) -> bool:
        """Returns True if the component is currently inside an entrypoint method.

        This is used to prevent recursive calls to entrypoint methods.
        """
        return getattr(self, "_inside_entrypoint", False)

    def _assert_inside_entrypoint(self, msg: str = "") -> None:
        """Assert that the component is inside an entrypoint method.

        Raises a RuntimeError if not.
        """
        if not self.inside_entrypoint:
            if msg:
                msg = f" {msg}"
            msg = f"An entrypoint for {self.instance_name} is not being executed.{msg}"
            raise RuntimeError(msg)

    def _assert_outside_entrypoint(self, msg: str = "") -> None:
        """Assert that the component is outside an entrypoint method.

        Raises a RuntimeError if not.
        """
        if self.inside_entrypoint:
            if msg:
                msg = f" {msg}"
            msg = f"An entrypoint for '{self.instance_name}' is already being executed.{msg}"
            raise RuntimeError(msg)

    def _before_entrypoint(self, entrypoint_name: str, *args, **kwargs) -> None:  # noqa: ARG002 as these are meant to be overridden
        self._assert_inside_entrypoint("Must not call '_before_entrypoint' outside an entrypoint method.")

    def _wrap_entrypoint[S: ComponentBase, **P, T](self: S, entrypoint: Callable[Concatenate[S, P], T], *args: P.args, **kwargs: P.kwargs) -> T:
        self._assert_inside_entrypoint("Must not call '_wrap_entrypoint' outside an entrypoint method.")

        with self.decimal.context_manager():
            return entrypoint(self, *args, **kwargs)

    def _after_entrypoint(self, entrypoint_name: str) -> None:  # noqa: ARG002 as these are meant to be overridden
        self._assert_inside_entrypoint("Must not call '_after_entrypoint' outside an entrypoint method.")


def component_entrypoint[T: ComponentBase, **P, R](entrypoint: Entrypoint[T, P, R]) -> Entrypoint[T, P, R]:
    return typing_cast("T", ComponentBase).component_entrypoint_decorator(entrypoint)
