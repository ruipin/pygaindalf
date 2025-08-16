# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import model_validator, BaseModel, ModelWrapValidatorHandler
from typing import Any, Self, ClassVar, override
from abc import ABCMeta, abstractmethod

from ...util.mixins import NamedProtocol

from .entity import Entity


class InstanceStoreEntityMixin(metaclass=ABCMeta):
    def __init_subclass__(cls) -> None:
        if not isinstance(cls, Entity):
            raise TypeError(f"{cls.__name__} must inherit from Entity to use InstanceStoreEntityMixin.")

    # MARK: Abstract Methods
    @classmethod
    @abstractmethod
    def _instance_store_search(cls, **kwargs) -> Entity | None:
        raise NotImplementedError("This method should be implemented by subclasses to find an existing instance based on the provided kwargs.")

    @classmethod
    @abstractmethod
    def _instance_store_add(cls, instance: Entity) -> None:
        raise NotImplementedError("This method should be implemented by subclasses to add an instance to the store.")


    # MARK: Create instance
    def __new__(cls, **kwargs):
        if (instance := cls._instance_store_search(**kwargs)) is None:
            instance = super().__new__(cls)
            instance.__dict__['initialized'] = False
        return instance


    # MARK: Handle (re-)initialization
    @model_validator(mode='wrap')
    @classmethod
    def _validate_singleton(cls, data: Any, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not issubclass(cls, BaseModel):
            raise TypeError(f"{cls.__name__} must be a subclass of BaseModel to use InstanceStoreEntityMixin.")

        if isinstance(data, cls):
            return data

        if not isinstance(data, dict):
            raise TypeError(f"Expected a dictionary for {cls.__name__}, got {type(data).__name__}.")

        # If an instance already exists, swap out its dictionary by an empty one as the constructor will run
        instance = cls._instance_store_search(**data)
        old_dict = None
        new_dict = None
        if instance is not None:
            old_dict = instance.__dict__
            new_dict = instance.__dict__ = {
                'initialized': True
            }

        # Do validation/initialization
        result = handler(data)

        if not isinstance(result, Entity):
            raise ValueError(f"Expected the handler to return an instance of {cls.__name__}, got {type(result).__name__}.")

        # If we were reinitializing an instance, compare the dictionaries - they must be the exact same
        if instance is not None:
            if result is not instance:
                raise ValueError(f"Re-initialization of {cls.__name__} returned a different instance than the existing one: {result} != {instance}.")
            if old_dict is None or new_dict is None:
                raise RuntimeError(f"The old_dict or new_dict variables should never be None here. This error should be unreachable, so something went terribly wrong!")
            instance.__dict__ = old_dict

            key_set = set(*old_dict.keys(), *new_dict.keys())
            for key in key_set:
                if not key:
                    raise ValueError(f"Key '{key}' in {cls.__name__} cannot be empty.")
                if key[0] == '_':
                    continue
                old_value = old_dict.get(key, None)
                new_value = new_dict.get(key, None)
                if isinstance(old_value, object):
                    if old_value is not new_value:
                        raise ValueError(f"Re-initialization of {cls.__name__} changed the instance's attribute object '{key}': {old_value} -> {new_value}")
                else:
                    if old_value != new_value:
                        raise ValueError(f"Re-initialization of {cls.__name__} changed the instance's attribute '{key}': {old_value} -> {new_value}")

        # Mark the result as initialized and return it
        result.__dict__['initialized'] = True
        cls._instance_store_add(result)
        return result



# MARK: Mixin for Named Instances
class NamedInstanceStoreEntityMixin(InstanceStoreEntityMixin, metaclass=ABCMeta):
    INSTANCES : ClassVar[dict[str, Entity]] = {}

    @classmethod
    @override
    def _instance_store_search(cls, **kwargs) -> Entity | None:
        instance_name = cls.calculate_instance_name_from_dict(kwargs)
        if instance_name is None:
            return None
        return cls.INSTANCES.get(instance_name, None)

    @classmethod
    @override
    def _instance_store_add(cls, instance: Entity) -> None:
        if not isinstance(instance, NamedProtocol):
            raise TypeError(f"Expected an instance of a class implementing NamedProtocol, got {type(instance).__name__}.")
        if (name := instance.instance_name) is None:
            raise ValueError(f"{cls.__name__} must have a valid 'instance_name' to be added to the instance store.")
        cls.INSTANCES[name] = instance

    @classmethod
    def instance(cls, instance_name: str) -> Entity | None:
        return cls.INSTANCES.get(instance_name)

    @classmethod
    @abstractmethod
    def calculate_instance_name_from_dict(cls, data : dict[str, Any]) -> str:
        raise NotImplementedError(f"{cls.__name__} must implement the 'calculate_instance_name_from_dict' method to generate a name for the instance.")