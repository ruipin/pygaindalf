# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import importlib
import functools
import inspect

from pydantic import ModelWrapValidatorHandler, ValidationInfo, model_validator
from typing import Any, Annotated, Callable, overload, TypeVar, override
from abc import ABCMeta, abstractmethod

from app.util.mixins import LoggableHierarchicalNamedMixin

from ..util.config.inherit import FieldInherit
from ..util.helpers.decimal import DecimalConfig, DecimalFactory

from ..util.helpers import classproperty
from ..util.config import BaseConfigModel


# MARK: Base Component Configuration
class BaseComponentConfig(BaseConfigModel, metaclass=ABCMeta):
    package : str

    decimal : DecimalConfig = FieldInherit(default_factory=DecimalConfig, description="Decimal configuration for provider")

    @model_validator(mode='wrap')
    @classmethod
    def _coerce_to_concrete_class(cls, data : Any, handler : ModelWrapValidatorHandler, info : ValidationInfo) -> 'BaseComponentConfig':
        # Already instantiated
        if isinstance(data, cls):
            return data

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
        if cls is concrete_cls:
            return handler(data)
        if not issubclass(concrete_cls, cls):
            raise TypeError(f"Expected configuration class {cls.__name__}, got {concrete_cls.__name__} instead.")

        return concrete_cls.model_validate(data)

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
        if not issubclass(config_cls, BaseComponentConfig):
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



# MARK: Component Field Descriptor
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



# MARK: Component subclassing mechanism
class ComponentSubclassMeta(LoggableHierarchicalNamedMixin, metaclass=ABCMeta):
    config = ComponentField(BaseComponentConfig)
    config_class : type[BaseComponentConfig]


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

            # Sanity check the parent classes for the same attribute
            for parent in mro:
                base_desc = getattr(parent.__dict__, attr, None)
                if base_desc is None:
                    continue
                if not isinstance(base_desc, ComponentField):
                    raise TypeError(f"{cls.__name__}.{attr} must be a ComponentField descriptor.")
                if not isinstance(desc_type, base_desc.type):
                    raise TypeError(f"{cls.__name__}.{attr} must be a subclass of {base_desc.type.__name__}.")

            # Create a class property for the descriptor
            setattr(cls, f'{attr}_class', classproperty(lambda cls: desc_type))

    def __init__(self, config : BaseComponentConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.config = config



# MARK: Component entrypoint decorator
def component_entrypoint[C,T](entrypoint: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator for component entrypoint methods.
    It does sanity checks, sets the local context, and calls the component's setup and teardown methods.
    """
    @functools.wraps(entrypoint)
    def wrapper(self : C, *args, **kwargs) -> T:
        if not isinstance(self, ComponentBase):
            raise TypeError(f"{entrypoint.__name__} must be called on a ComponentBase instance, got {type(self).__name__} instead.")

        # If the component is already inside an entrypoint, we just call the entrypoint directly.
        if self.inside_entrypoint:
            result = entrypoint(self, *args, **kwargs)
        else:
            try:
                self._inside_entrypoint = True

                self.before_entrypoint(entrypoint.__name__, *args, **kwargs)

                try:
                    result = self.wrap_entrypoint(entrypoint, *args, **kwargs)
                finally:
                    self.after_entrypoint(entrypoint.__name__)
            finally:
                self._inside_entrypoint = False

        return result

    wrapper.__dict__['component_entrypoint'] = True
    return wrapper



# MARK: Component Base Class
class ComponentBase(ComponentSubclassMeta, metaclass=ABCMeta):
    # Decimal factory for precise calculations
    decimal : DecimalFactory

    def __init__(self, config : BaseComponentConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self._inside_entrypoint = False

        self.decimal = DecimalFactory(self.config.decimal)

    @property
    def inside_entrypoint(self) -> bool:
        """
        Returns True if the component is currently inside an entrypoint method.
        This is used to prevent recursive calls to entrypoint methods.
        """
        return self._inside_entrypoint if hasattr(self, '_inside_entrypoint') else False

    def _assert_inside_entrypoint(self, msg : str = '') -> None:
        """
        Assert that the component is inside an entrypoint method.
        Raises a RuntimeError if not.
        """
        if not self.inside_entrypoint:
            if msg: msg = f" {msg}"
            raise RuntimeError(f"An entrypoint for {self.instance_name} is not being executed.{msg}")

    def _assert_outside_entrypoint(self, msg : str = '') -> None:
        """
        Assert that the component is outside an entrypoint method.
        Raises a RuntimeError if not.
        """
        if self.inside_entrypoint:
            if msg: msg = f" {msg}"
            raise RuntimeError(f"An entrypoint for '{self.instance_name}' is already being executed.{msg}")

    def before_entrypoint(self, entrypoint_name : str, *args, **kwargs) -> None:
        self._assert_inside_entrypoint("Must not call 'before_entrypoint' outside an entrypoint method.")

    def wrap_entrypoint[T](self, entrypoint : Callable[..., T], *args, **kwargs) -> T:
        self._assert_inside_entrypoint("Must not call 'wrap_entrypoint' outside an entrypoint method.")

        with self.decimal.context_manager():
            return entrypoint(self, *args, **kwargs)

    def after_entrypoint(self, entrypoint_name : str) -> None:
        self._assert_inside_entrypoint("Must not call 'after_entrypoint' outside an entrypoint method.")

    @override
    def __getattribute__(self, name: str) -> Any:
        obj = super().__getattribute__(name)

        # If the object is a child class method and not a component entrypoint, raise an error as that likely means someone is trying to call it directly.
        # This is of course not fool-proof (and anyone who really wants to call us will be able to bypass this), but it is a good way to prevent accidental misuse.
        if inspect.ismethod(obj) and not hasattr(ComponentBase, name):
            is_entrypoint = getattr(obj, 'component_entrypoint', False)
            if not is_entrypoint and not self.inside_entrypoint:
                    raise RuntimeError(f"Method '{name}' is not a component entrypoint. Must call it through the component's entrypoint method.")

        return obj
