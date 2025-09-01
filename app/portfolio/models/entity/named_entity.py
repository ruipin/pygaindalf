# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override, Any, Self, ClassVar
from abc import ABCMeta, abstractmethod
from pydantic import computed_field, Field, field_validator, model_validator

from ....util.mixins import NamedMixinMinimal, NamedProtocol

from ..uid import Uid

from . import Entity


class NamedEntity(Entity, NamedMixinMinimal, metaclass=ABCMeta):
    STRICT_INSTANCE_NAME_VALIDATION : ClassVar[bool] = True

    @classmethod
    @override
    def _calculate_uid(cls, data : dict[str, Any]) -> Uid:
        instance_name = cls.calculate_instance_name_from_dict(data)
        if instance_name is None:
            raise ValueError(f"{cls.__name__} must not have the default instance name when calculating its UID. Please set instance_name before using NamedUidMixin.")

        return Uid(namespace=cls.uid_namespace(data), id=instance_name)

    @classmethod
    @abstractmethod
    def calculate_instance_name_from_dict(cls, data : dict[str, Any]) -> str:
        raise NotImplementedError(f"{cls.__name__} must implement the 'calculate_instance_name_from_dict' method to generate a name for the instance.")

    @classmethod
    def calculate_instance_name_from_instance(cls, instance : 'Entity') -> str:
        if not isinstance(instance, NamedProtocol):
            raise TypeError(f"Expected instance of {cls.__name__}, got {type(instance).__name__}.")
        if (name := instance.instance_name) is not None:
            return name
        raise ValueError(f"{cls.__name__} must have a valid instance name.")

    @classmethod
    def calculate_instance_name_from_arbitrary_data(cls, data : Any) -> str:
        if isinstance(data, cls):
            return cls.calculate_instance_name_from_instance(data)
        if not isinstance(data, dict):
            raise TypeError(f"Expected 'data' to be a dict or {cls.__name__}, got {type(data).__name__}.")
        return cls.calculate_instance_name_from_dict(data)

    @model_validator(mode='after')
    def _validate_instance_name(self) -> Self:
        if self.__class__.STRICT_INSTANCE_NAME_VALIDATION:
            dict_name = self.__class__.calculate_instance_name_from_dict(self.__dict__)
            instance_name = self.__class__.calculate_instance_name_from_instance(self)
            if instance_name != dict_name:
                raise ValueError(f"Instance name '{instance_name}' does not match the calculated name from the dictionary '{dict_name}'.")

        return self

    @override
    def __str__(self) -> str:
        return super().__str__().replace('>', f" v{self.version}>")

    @override
    def __repr__(self) -> str:
        return super().__repr__().replace('>', f" v{self.version}>")



class ManualNamedEntity(NamedEntity, metaclass=ABCMeta):
    instance_name : str = Field(min_length=1, description="Name of the entity.")

    @classmethod
    @override
    def calculate_instance_name_from_dict(cls, data : dict[str, Any]) -> str:
        if not (name := data.get('instance_name', None)):
            raise ValueError(f"{cls.__name__} must have an 'instance_name' field in the data to generate a name for the instance.")
        return name


class AutomaticNamedEntity(NamedEntity, metaclass=ABCMeta):
    PROPAGATE_INSTANCE_NAME_FROM_PARENT : ClassVar[bool] = False

    @classmethod
    @override
    def _calculate_uid(cls, data : dict[str, Any]) -> Uid:
        instance_name = cls.calculate_instance_name_from_dict(data)
        if instance_name is None:
            raise ValueError(f"{cls.__name__} must not have the default instance name when calculating its UID. Please set instance_name before using NamedUidMixin.")

        return Uid(namespace=cls.uid_namespace(data), id=instance_name)

    @classmethod
    @override
    @abstractmethod
    def calculate_instance_name_from_dict(cls, data : dict[str, Any]) -> str:
        raise NotImplementedError(f"{cls.__name__} must implement the 'calculate_instance_name_from_dict' method to generate a name for the instance.")

    @computed_field
    @property
    def instance_name(self) -> str:
        """
        Get the instance name, or class name if not set.
        """
        return self.calculate_instance_name_from_dict(self.__dict__)