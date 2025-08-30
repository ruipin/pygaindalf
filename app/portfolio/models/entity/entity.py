# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import sys

from pydantic import BaseModel, ConfigDict, ModelWrapValidatorHandler, ValidationInfo, model_validator, Field, field_validator, computed_field, model_validator, PositiveInt, PositiveInt, PrivateAttr
from typing import override, Any, ClassVar, MutableMapping, TYPE_CHECKING, ContextManager
from abc import abstractmethod, ABCMeta
from weakref import WeakValueDictionary
from functools import cached_property

from ....util.mixins import LoggableHierarchicalModel, NamedProtocol
from ....util.helpers import script_info
from ....util.helpers.callguard import callguard_class

if TYPE_CHECKING:
    from ...journal.entity_journal import EntityJournal
    from ...journal.session_manager import SessionManager
    from ...journal.session import Session

from ..uid import Uid
from .audit import EntityAuditLog



@callguard_class()
class Entity(LoggableHierarchicalModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        validate_assignment=True,
    )


    # MARK: Uid
    uid : Uid = Field(default=None, validate_default=True, description="Unique identifier for the entity.") # pyright: ignore[reportAssignmentType] as the default value is overridden by _validate_uid_before anyway

    _UID_STORAGE : 'ClassVar[MutableMapping[Uid, Entity]]' = WeakValueDictionary() # Class variable to store UIDs of all instances of this class. Used to check for duplicate UIDs.

    if script_info.is_unit_test():
        @classmethod
        def reset_state(cls) -> None:
            cls._UID_STORAGE.clear()

    @classmethod
    def uid_namespace(cls, data : dict[str, Any] | None = None) -> str:
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
    def _validate_uid_before(cls, data: Any, info: ValidationInfo) -> 'Entity':
        if (uid := data.get('uid', None)) is None:
            uid = {}

        if not isinstance(uid, Uid):
            uid = cls._calculate_uid(data)

        if not isinstance(uid, Uid):
            raise TypeError(f"Expected 'uid' to be of type Uid, got {type(uid).__name__}.")

        uid_namespace = cls.uid_namespace(data)
        if uid.namespace != uid_namespace:
            raise ValueError(f"Uid namespace '{uid.namespace}' does not match expected namespace '{uid_namespace}'.")

        data['uid'] = uid
        return data

    @model_validator(mode='after')
    def _validate_uid_after(self, info: ValidationInfo) -> 'Entity':
        # Get a reference to the UID storage
        uid_storage = self.__class__._get_uid_storage()

        # If the entity already exists, we fail unless we are cloning the entity and incrementing the version
        existing = uid_storage.get(self.uid, None)
        if existing and existing is not self:
            if (self.version <= existing.version):
                raise ValueError(f"Duplicate UID detected: {self.uid} with versions {self.version} vs {existing.version}. Each entity must have a unique UID or increment the version.")

        # Store the entity in the UID storage
        uid_storage[self.uid] = self

        return self


    @classmethod
    def _get_uid_storage(cls) -> 'MutableMapping[Uid, Entity]':
        if (uid_storage := cls._UID_STORAGE) is None:
            raise ValueError(f"{cls.__name__} must have a valid UID storage. The UID_STORAGE class variable cannot be None.")
        return uid_storage

    @classmethod
    def by_uid[T : 'Entity'](cls : type[T], uid: Uid) -> T | None:
        result = cls._get_uid_storage().get(uid, None)
        if not isinstance(result, cls):
            raise ValueError(f"UID storage returned an instance of {type(result).__name__} instead of {cls.__name__}.")
        return result


    # MARK: Instance Name
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


    # MARK: Meta
    _initialized : bool = PrivateAttr(default=False)
    entity_log : EntityAuditLog = Field(default_factory=lambda data: EntityAuditLog(data['uid']), validate_default=True, repr=False, exclude=True, description="The audit log for this entity, which tracks changes made to it over time.")
    version    : PositiveInt    = Field(default_factory=lambda data: data['entity_log'].next_version, validate_default=True, ge=1, description="The version of this entity. Incremented when the entity is cloned as part of an update action.")

    @field_validator('entity_log', mode='after')
    @classmethod
    def _validate_audit_log(cls, entity_log: EntityAuditLog, info: ValidationInfo) -> EntityAuditLog:
        if (uid := info.data.get('uid', None)) is None or not isinstance(uid, Uid):
            raise ValueError(f"Entity must have a valid 'uid' to validate the audit log. Found: {uid}.")
        if entity_log.entity_uid != uid:
            raise ValueError(f"Audit log UID '{entity_log.entity_uid}' does not match entity UID '{uid}'.")
        return entity_log

    @field_validator('version', mode='after')
    @classmethod
    def _validate_version(cls, version: PositiveInt, info: ValidationInfo) -> PositiveInt:
        if (entity_log := info.data.get('entity_log', None)) is None or not isinstance(entity_log, EntityAuditLog):
            raise ValueError(f"Entity must have a valid 'entity_log' to validate the version. Found: {entity_log}.")
        if version != entity_log.next_version:
            raise ValueError(f"Entity version '{version}' does not match the next audit log version '{entity_log.version + 1}'. The version should be incremented when the entity is cloned as part of an update action.")
        return version

    @override
    def model_post_init(self, context : Any) -> None:
        super().model_post_init(context)

        self.entity_log.on_create(self)
        self._intialized = True

    def __del__(self):
        # No need to track deletion in finalizing state
        if not sys.is_finalizing and not self.superseded:
            self.entity_log.on_delete(self, who='system', why='__del__')

    @computed_field
    @property
    def superseded(self) -> bool:
        """
        Indicates whether this entity instance has been superseded by another instance with an incremented version.
        """
        return self.entity_log.version > self.version

    @property
    def initialized(self) -> bool:
        try:
            return getattr(self, '_initialized', False)
        except:
            return False

    def update[T : Entity](self : T, **kwargs: Any) -> T:
        """
        Creates a new instance of the entity with the updated data.
        The new instance will have an incremented version and the same UID, superseding the current instance.
        """
        if not kwargs:
            raise ValueError("No data provided to update the entity.")

        if 'uid' in kwargs:
            raise ValueError("Cannot update the 'uid' of an entity. The UID is immutable and should not be changed.")
        if 'version' in kwargs:
            raise ValueError("Cannot update the 'version' of an entity. The version is managed by the entity itself and should not be changed directly.")

        args = {}
        for field_name in self.__class__.model_fields.keys():
            if field_name in kwargs:
                args[field_name] = kwargs[field_name]
            else:
                args[field_name] = getattr(self, field_name)

        args.update(kwargs)
        args['uid'    ] = self.uid
        args['version'] = self.entity_log.next_version

        return self.__class__(**args)


    # MARK: Journal
    @property
    def journal(self) -> 'EntityJournal':
        if self.superseded:
            raise RuntimeError("Cannot access the journal of a superseded entity.")
        return self.session.get_entity_journal(entity=self)

    @property
    def session(self) -> 'Session':
        manager = self.session_manager
        session = manager.session
        if session is None:
            raise RuntimeError("No active session found in the session manager.")

        return session

    @cached_property
    def session_manager(self) -> 'SessionManager':
        parent = self.instance_parent
        if not isinstance(parent, Entity):
            raise ValueError(f"Entity must have an instance parent of type Entity to access the journal manager. Found: {type(parent).__name__}.")

        return parent.session_manager

    @override
    def __getattribute__(self, name: str) -> Any:
        # Short-circuit a few attributes to avoid recursion
        if name.startswith('_') or name in ('initialized', 'session_manager', 'session', 'instance_parent'):
            return super().__getattribute__(name)

        # Short-circuit if not yet initialized
        if not self.initialized:
            return super().__getattribute__(name)

        # If not in a session, return the normal attribute
        if self.superseded or not self.session_manager.in_session:
            return super().__getattribute__(name)

        # Otherwise, use the journal to get the attribute
        return self.journal.get(name)

    @override
    def __setattr__(self, name: str, value: Any) -> None:
        # Short-circuit private attributes
        if name.startswith('_'):
            return super().__setattr__(name, value)

        # Short-circuit if not yet initialized
        if not self._initialized:
            return super().__setattr__(name, value)

        # If not in a session, set the normal attribute
        if self.superseded or not self.session_manager.in_session:
            return super().__setattr__(name, value)

        # Otherwise, use the journal to set the attribute
        self.journal.set(name, value)

    @property
    def dirty(self) -> bool:
        if self.superseded:
            return False
        return self.journal.dirty

    @property
    def stale(self) -> bool:
        return self.superseded or self.dirty


    # MARK: Utilities
    @override
    def __hash__(self):
        return hash(self.uid)