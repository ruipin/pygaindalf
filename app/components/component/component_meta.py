# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import inspect

from abc import ABCMeta
from typing import Any, TypeVar
from typing import cast as typing_cast

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from app.util.mixins import LoggableHierarchicalNamedMixin

from ...util.callguard import CALLGUARD_ENABLED
from ...util.helpers import generics
from .component_config import ComponentConfig


# MARK: Component subclassing mechanism
class ComponentMeta[C: ComponentConfig](LoggableHierarchicalNamedMixin, metaclass=ABCMeta):
    config: C
    config_class: type[C]

    @classmethod
    def _introspect_config_class(cls) -> type[C]:
        """Introspects the class to find the configuration class."""
        arg = generics.get_parent_argument(cls, ComponentMeta, "C")
        return typing_cast("type[C]", arg)

    @classmethod
    def __init_subclass__(cls, **kwargs) -> None:
        """Validate that all ComponentField descriptors are subclasses of their base class and create a '*_class' property for each descriptor."""
        super().__init_subclass__(**kwargs)

        # Introspect the original bases to get the configuration class
        cls.config_class = cls._introspect_config_class()
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
