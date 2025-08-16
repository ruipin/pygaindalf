# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import BaseModel, ConfigDict, ModelWrapValidatorHandler, ValidationInfo, model_validator, Field, field_validator, computed_field, model_validator
from typing import override, Any, ClassVar, MutableMapping
from abc import abstractmethod, ABCMeta
from weakref import WeakValueDictionary

from ....util.mixins import LoggableHierarchicalModel, NamedProtocol
from ....util.helpers import classproperty

from ..uid import Uid

from ..meta_data import EntityMetaData



# MARK: Entity
class Entity(LoggableHierarchicalModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        #validate_assignment=True,
    )


    # MARK: Entity - Uid
    uid : Uid = Field(frozen=True, description="Unique identifier for the entity.")

    UID_STORAGE : 'ClassVar[MutableMapping[Uid, Entity]]' = WeakValueDictionary() # Class variable to store UIDs of all instances of this class. Used to check for duplicate UIDs.

    @classmethod
    def uid_namespace(cls, data : dict[str, Any]) -> str:
        """
        Returns the namespace for the UID.
        This can be overridden in subclasses to provide a custom namespace.
        """
        return cls.__name__

    @classmethod
    def _calculate_uid(cls, data : dict[str, Any]) -> Uid:
        raise NotImplementedError(f"{cls.__name__} must implement the '_calculate_uid' method to generate a UID.")

    @model_validator(mode='before')
    @classmethod
    def _validate_uid_before(cls, data: Any, info: ValidationInfo) -> Uid:
        if (uid := data.get('uid', None)) is None:
            uid = {}

        if not isinstance(uid, Uid):
            uid = cls._calculate_uid(data)

        if not isinstance(uid, Uid):
            raise TypeError(f"Expected 'uid' to be of type Uid, got {type(uid).__name__}.")

        uid_namespace = cls.uid_namespace(data)
        if uid.namespace != uid_namespace:
            raise ValueError(f"Uid namespace '{uid.namespace}' does not match expected namespace '{uid_namespace}'.")

        return uid

    @model_validator(mode='after')
    def _validate_uid_after(self, info: ValidationInfo) -> 'Entity':
        # Get a reference to the UID storage
        uid_storage = self.__class__._get_uid_storage()

        # If the entity already exists, we fail unless we are cloning the entity and incrementing the version
        existing = uid_storage.get(self.uid, None)
        if existing:
            if (\
                (context := info.context) is None or \
                (not isinstance(context, dict)) or \
                (context_entity := context.get('existing_entity', None)) is None or \
                (context_entity.uid is not existing) or \
                (self.version <= existing.version)
            ):
                raise ValueError(f"Duplicate UID detected: {self.uid}. Each entity must have a unique UID or increment the version.")

        # Store the entity in the UID storage
        uid_storage[self.uid] = self

        return self


    @classmethod
    def _get_uid_storage(cls) -> 'MutableMapping[Uid, Entity]':
        if (uid_storage := cls.UID_STORAGE) is None:
            raise ValueError(f"{cls.__name__} must have a valid UID storage. The UID_STORAGE class variable cannot be None.")
        return uid_storage

    @classmethod
    def from_uid(cls, uid: Uid) -> 'Entity | None':
        return cls._get_uid_storage().get(uid, None)

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


    # MARK: Entity - Meta
    meta : EntityMetaData = Field(default_factory=EntityMetaData, description="Metadata associated with the entity.", json_schema_extra={'keep_on_reinit': True})

    @property
    def version(self):
        return self.meta.version


    # MARK: Entity - Utilities
    @override
    def __hash__(self):
        return hash(self.uid)