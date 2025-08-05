# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import importlib

from pydantic import ModelWrapValidatorHandler, ValidationInfo, model_validator
from typing import Any, Annotated, Callable, overload, TypeVar
from abc import ABCMeta, abstractmethod

from app.util.mixins import LoggableHierarchicalNamedMixin

from ..util.helpers import classproperty
from ..util.config import ConfigBaseModel


class ComponentBaseConfig(ConfigBaseModel, metaclass=ABCMeta):
    package : str

    @model_validator(mode='wrap')
    @classmethod
    def _validate(cls, data : Any, handler : ModelWrapValidatorHandler, info : ValidationInfo) -> 'ComponentBaseConfig':
        # Already instantiated
        if isinstance(data, cls):
            return data

        # Concrete class already resolved
        if isinstance(info.context, dict):
            concrete_cls = info.context.get('concrete_class', None)
            if concrete_cls is not None:
                if cls is not concrete_cls:
                    raise TypeError(f"Expected {cls.__name__} configuration, got {concrete_cls.__name__} instead.")
                return handler(data)

        # Must be a dictionary
        if not isinstance(data, dict):
            raise TypeError(f"Expected a dictionary for {cls.__name__} configuration, got {type(data).__name__}.")

        package = data.get('package', None)
        if package is None:
            raise ValueError(f"Missing 'package' key in {cls.__name__} configuration.")

        # Get the concrete configuration class for this package
        component_cls = cls.get_component_class_for_package(package)

        concrete_cls = getattr(component_cls, 'config_class', None)
        if concrete_cls is None:
            raise ImportError(f"Configuration class for {package} does not define 'config_class'.")
        if not issubclass(concrete_cls, cls):
            raise TypeError(f"Expected configuration class {cls.__name__}, got {concrete_cls.__name__} instead.")

        # Construct concrete class
        return concrete_cls.model_validate(data, context={'concrete_class': concrete_cls})

    @classmethod
    def get_component_class_for_package(cls, package) -> type['ComponentBase']:
        # Import the package
        root_path = cls.package_root
        rel_path = f'.{package}'
        path = f'{root_path}{rel_path}'
        mod = importlib.import_module(f'.{package}', root_path)

        # Get the component class
        component_cls = getattr(mod, 'COMPONENT', None)
        if component_cls is None:
            raise ImportError(f"Configuration class for {package} not found in '{path}'.")
        if not isinstance(component_cls, type):
            raise TypeError(f"Expected a class for {package} component, got {type(component_cls).__name__} instead.")

        # Sanity check the configuration class
        config_cls = getattr(component_cls, 'config_class', None)
        if config_cls is None:
            raise ImportError(f"Configuration class for {package} does not define 'config_class'.")
        if not issubclass(config_cls, ComponentBaseConfig):
            raise TypeError(f"Expected configuration class {cls.__name__}, got {config_cls.__name__} instead.")

        # Done
        return component_cls

    @property
    def component_class(self) -> type['ComponentBase']:
        return self.get_component_class_for_package(self.package)

    @classproperty
    @abstractmethod
    def package_root(cls) -> str:
        raise NotImplementedError(f"{cls.__name__}.package_root() must be implemented.")


class ComponentField[T]:
    def __init__(self, cls : type[T]):
        self.type = cls

    def __set_name__(self, owner : type, name : str):
        self.attr = f'_{name}'

    @overload
    def __get__(self, obj: None, objtype: type) -> 'ComponentField[T]': ...
    @overload
    def __get__(self, obj: Any, objtype: type) -> T: ...

    def __get__(self, obj, objtype=None) -> 'T | ComponentField[T]':
        if obj is None:
            return self
        if not hasattr(obj, self.attr):
            raise AttributeError(f"{obj.__class__.__name__} 'config' was not initialized.")
        return getattr(obj, self.attr)

    def __set__(self, obj, value : T):
        if not isinstance(value, self.type):
            raise TypeError(f"Expected {self.type.__name__}, got {type(value).__name__} instead.")
        setattr(obj, self.attr, value)
        obj.__set_name__(obj.__class__, self.attr)



class ComponentBase(LoggableHierarchicalNamedMixin, metaclass=ABCMeta):
    config = ComponentField(ComponentBaseConfig)
    config_class : type[ComponentBaseConfig]

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """
        Validate that all ComponentField descriptors in the subclass are subclasses of their base class types and create a '*_class' property for each descriptor.
        """
        super().__init_subclass__(**kwargs)

        mro = cls.__mro__
        attrs = list(cls.__dict__.keys())

        for attr in attrs:
            desc = getattr(cls, attr, None)
            if desc is None or not isinstance(desc, ComponentField):
                continue
            desc_type = desc.type

            for parent in mro:
                base_desc = getattr(parent.__dict__, attr, None)
                if base_desc is None:
                    continue
                if not isinstance(base_desc, ComponentField):
                    raise TypeError(f"{cls.__name__}.{attr} must be a ComponentField descriptor.")
                if not isinstance(desc_type, base_desc.type):
                    raise TypeError(f"{cls.__name__}.{attr} must be a subclass of {base_desc.type.__name__}.")

            setattr(cls, f'{attr}_class', classproperty(lambda cls: desc_type))

    def __init__(self, config : ComponentBaseConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.config = config
