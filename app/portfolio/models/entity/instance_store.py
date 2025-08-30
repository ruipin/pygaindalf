# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import model_validator, BaseModel, ModelWrapValidatorHandler, PrivateAttr
from typing import Any, Self, ClassVar, override
from abc import ABCMeta, abstractmethod

from ....util.mixins import NamedProtocol
from ....util.helpers import script_info

from . import Entity


class InstanceStoreEntityMixin(metaclass=ABCMeta):
    __initialized : bool = PrivateAttr(default=False)

    def __init_subclass__(cls) -> None:
        if (not issubclass(cls, Entity)) and (type(cls) is not ABCMeta):
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
        version = kwargs.get('version', None)

        if (instance := cls._instance_store_search(**kwargs)) is None or (version is not None and version == instance.entity_log.next_version):
            instance = super().__new__(cls)
            instance.__initialized = False
        return instance


    # MARK: Handle (re-)initialization
    def __init__(self, **kwargs):
        if not isinstance(self, Entity):
            raise TypeError(f"{self.__class__.__name__} must inherit from Entity to use InstanceStoreEntityMixin.")

        if not self.__initialized:
            super().__init__(**kwargs)
            self.__class__._instance_store_add(self)
        else:
            self._validate_reinitialization(kwargs)


    def _validate_reinitialization(self, data : dict[str, Any]) -> None:
        if not isinstance(self, Entity):
            raise TypeError(f"{self.__class__.__name__} must inherit from Entity to use InstanceStoreEntityMixin.")

        keys = set()

        for key, info in self.__class__.model_fields.items():
            if info.init == False or info.exclude == True:
                if key in data:
                    raise ValueError(f"Field '{key}' cannot be set during reinitialization of {self.__class__.__name__}.")
                continue

            # Check if the field is optional
            if key not in data:
                if info.is_required():
                    raise ValueError(f"Field '{key}' is required for reinitialization of {self.__class__.__name__}.")
                continue

            # Try to coerce
            data_value = data.get(key, None)
            self_value = self.__dict__.get(key, None)

            if self_value is None:
                if data_value is not None:
                    raise ValueError(f"Field '{key}' cannot be set during reinitialization of {self.__class__.__name__}.")
                continue

            self_type = type(self_value)
            if not isinstance(data_value, self_type):
                coerced = self_type(data_value)
                if not isinstance(coerced, self_type):
                    raise TypeError(f"Cannot coerce field '{key}' from {type(data_value).__name__} to {self_type.__name__} for reinitialization of {self.__class__.__name__}.")
                data_value = coerced

            if isinstance(self_value, Entity) or (eq := getattr(self_value, '__eq__', None)) is None or (eq_res := eq(data_value)) is NotImplemented:
                if self_value is not data_value:
                    raise TypeError(f"Field '{key}' cannot be set during reinitialization of {self.__class__.__name__} because it is not the existing value.")
            else:
                if (not eq_res):
                    raise TypeError(f"Field '{key}' cannot be set during reinitialization of {self.__class__.__name__} because it is not equal to the existing value.")

            keys.add(key)

        data_keys = set(data.keys())
        keys_diff = keys ^ data_keys
        if keys_diff:
            raise ValueError(f"Fields {keys_diff} cannot be set during reinitialization of {self.__class__.__name__}")






# MARK: Mixin for Named Instances
class NamedInstanceStoreEntityMixin(InstanceStoreEntityMixin, metaclass=ABCMeta):
    INSTANCES : ClassVar[dict[str, Entity]] = {}

    if script_info.is_unit_test():
        @classmethod
        def reset_state(cls) -> None:
            cls.INSTANCES.clear()

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