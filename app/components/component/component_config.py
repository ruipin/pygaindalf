# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import importlib

from abc import ABCMeta
from typing import TYPE_CHECKING, Any

from pydantic import Field, ModelWrapValidatorHandler, model_validator

from ...util.config import BaseConfigModel
from ...util.config.inherit import FieldInherit
from ...util.helpers import classproperty
from ...util.helpers.decimal import DecimalConfig


if TYPE_CHECKING:
    from .component_meta import ComponentMeta


# MARK: Base Component Configuration
class BaseComponentConfig(BaseConfigModel, metaclass=ABCMeta):
    package: str = Field(description="Package name of the component to load")

    title: str | None = Field(default=None, description="Logical title of the component instance, to help identification")

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
    def get_component_class_for_package(cls, package: str) -> type[ComponentMeta]:
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
    def component_class(self) -> type[ComponentMeta]:
        return self.get_component_class_for_package(self.package)

    @classproperty
    def package_root(cls) -> str:
        return "app.components"

    def create_component(self, *args, **kwargs) -> ComponentMeta:
        component_cls = self.component_class
        return component_cls(self, *args, **kwargs)
