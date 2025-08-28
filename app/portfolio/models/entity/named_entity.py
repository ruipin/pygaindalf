# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override, Any, Self, ClassVar
from abc import ABCMeta, abstractmethod
from pydantic import computed_field, Field, field_validator, model_validator

from ....util.mixins import NamedMixinMinimal

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

    @model_validator(mode='after')
    def _validate_instance_name(self) -> Self:
        if self.__class__.STRICT_INSTANCE_NAME_VALIDATION:
            instance_name = self.__class__.calculate_instance_name_from_instance(self)
            dict_name = self.__class__.calculate_instance_name_from_dict(self.__dict__)
            if instance_name != dict_name:
                raise ValueError(f"Instance name '{instance_name}' does not match the calculated name from the dictionary '{dict_name}'.")
        return self



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