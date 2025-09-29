# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Any, Self, override

from pydantic import PrivateAttr

from ....util.helpers import mro
from ....util.mixins import NamedProtocol
from . import Entity


if TYPE_CHECKING:
    from app.portfolio.models.store.string_uid_mapping import StringUidMapping


class InstanceStoreEntityMixin(Entity if TYPE_CHECKING else object, metaclass=ABCMeta):
    __initialized: bool = PrivateAttr(default=False)

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        mro.ensure_mro_order(cls, InstanceStoreEntityMixin, before=Entity)

    # MARK: Abstract Methods
    @classmethod
    @abstractmethod
    def _instance_store_search(cls, **kwargs) -> Self | None:
        msg = "This method should be implemented by subclasses to find an existing instance based on the provided kwargs."
        raise NotImplementedError(msg)

    @classmethod
    @abstractmethod
    def _instance_store_add(cls, instance: Self) -> None:
        msg = "This method should be implemented by subclasses to add an instance to the store."
        raise NotImplementedError(msg)

    # MARK: Create instance
    def __new__(cls, **kwargs) -> Self:
        version = kwargs.get("version")

        if (instance := cls._instance_store_search(**kwargs)) is None or (version is not None and version == instance.entity_log.next_version):
            instance = super().__new__(cls)
            instance.__initialized = False
        return instance

    # MARK: Handle (re-)initialization
    def __init__(self, **kwargs) -> None:
        if not self.__initialized:
            super().__init__(**kwargs)
            self._instance_store_add(self)
        else:
            self._validate_reinitialization(kwargs)

    def _validate_reinitialization(self, data: dict[str, Any]) -> None:
        keys = set()

        for key, info in type(self).model_fields.items():
            if info.init is False or info.exclude is True:
                if key in data:
                    msg = f"Field '{key}' cannot be set during reinitialization of {type(self).__name__}."
                    raise ValueError(msg)
                continue

            # Check if the field is optional
            if key not in data:
                if info.is_required():
                    msg = f"Field '{key}' is required for reinitialization of {type(self).__name__}."
                    raise ValueError(msg)
                continue

            # Try to coerce
            data_value = data.get(key)
            self_value = self.__dict__.get(key, None)

            if self_value is None:
                if data_value is not None:
                    msg = f"Field '{key}' cannot be set during reinitialization of {type(self).__name__}."
                    raise ValueError(msg)
                continue

            self_type = type(self_value)
            if not isinstance(data_value, self_type):
                coerced = self_type(data_value)
                if not isinstance(coerced, self_type):
                    msg = f"Cannot coerce field '{key}' from {type(data_value).__name__} to {self_type.__name__} for reinitialization of {type(self).__name__}."
                    raise TypeError(msg)
                data_value = coerced

            if isinstance(self_value, Entity) or (eq := getattr(self_value, "__eq__", None)) is None or (eq_res := eq(data_value)) is NotImplemented:
                if self_value is not data_value:
                    msg = f"Field '{key}' cannot be set during reinitialization of {type(self).__name__} because it is not the existing value."
                    raise TypeError(msg)
            else:
                if not eq_res:
                    msg = f"Field '{key}' cannot be set during reinitialization of {type(self).__name__} because it is not equal to the existing value."
                    raise TypeError(msg)

            keys.add(key)

        data_keys = set(data.keys())
        keys_diff = keys ^ data_keys
        if keys_diff:
            msg = f"Fields {keys_diff} cannot be set during reinitialization of {type(self).__name__}"
            raise ValueError(msg)


# MARK: Mixin for Named Instances
class NamedInstanceStoreEntityMixin(InstanceStoreEntityMixin, metaclass=ABCMeta):
    @classmethod
    def _get_name_store(cls) -> StringUidMapping:
        return cls._get_entity_store().get_string_uid_mapping(cls.__name__)

    @classmethod
    @override
    def _instance_store_search(cls, **kwargs) -> Entity | None:
        instance_name = cls.calculate_instance_name_from_dict(kwargs)
        if instance_name is None:
            return None

        return cls.instance(instance_name)

    @classmethod
    @override
    def _instance_store_add(cls, instance: Entity) -> None:
        if not isinstance(instance, NamedProtocol):
            msg = f"Expected an instance of a class implementing NamedProtocol, got {type(instance).__name__}."
            raise TypeError(msg)
        if (name := instance.instance_name) is None:
            msg = f"{cls.__name__} must have a valid 'instance_name' to be added to the instance store."
            raise ValueError(msg)
        cls._get_name_store()[name] = instance.uid

    @classmethod
    def instance(cls, instance_name: str) -> Entity | None:
        uid = cls._get_name_store().get(instance_name, None)
        if uid is None:
            return uid
        return cls._get_entity_store()[uid]

    @classmethod
    @abstractmethod
    @override
    def calculate_instance_name_from_dict(cls, data: dict[str, Any]) -> str:
        msg = f"{cls.__name__} must implement the 'calculate_instance_name_from_dict' method to generate a name for the instance."
        raise NotImplementedError(msg)
