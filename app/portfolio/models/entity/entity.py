# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import sys
import functools

from frozendict import frozendict
from pydantic import BaseModel, ConfigDict, ModelWrapValidatorHandler, ValidationInfo, model_validator, Field, field_validator, computed_field, model_validator, PositiveInt, PositiveInt, PrivateAttr
from typing import override, Any, ClassVar, MutableMapping, TYPE_CHECKING, ContextManager, Self, Unpack, cast as typing_cast
from abc import abstractmethod, ABCMeta
from weakref import WeakValueDictionary
from functools import cached_property

from ....util.mixins import LoggableHierarchicalModel, NamedProtocol
from ....util.helpers import script_info
from ....util.helpers.callguard import CallguardClassOptions

if TYPE_CHECKING:
    from ...journal.entity import EntityJournal
    from ...journal.session_manager import SessionManager
    from ...journal.session import JournalSession

from ..uid import Uid

from .superseded import superseded_check
from .audit import EntityAuditLog


class Entity(LoggableHierarchicalModel):
    __callguard_class_options__ = CallguardClassOptions['Entity'](
        decorator=superseded_check, decorate_public_methods=True, decorate_skip_properties=True
    )

    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        validate_assignment=True,
    )


    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

        # Collect field aliases into a single collection
        aliases : dict[str,str] = dict()
        reverse : dict[str,str] = dict()

        for name, info in cls.model_fields.items():
            if info.alias:
                aliases[info.alias] = name
                reverse[name] = info.alias

        cls.model_field_aliases = frozendict(aliases)
        cls.model_field_reverse_aliases = frozendict(reverse)

    # MARK: Uid
    uid : Uid = Field(default_factory=lambda: None, validate_default=True, description="Unique identifier for the entity.") # pyright: ignore[reportAssignmentType] as the default value is overridden by _validate_uid_before anyway

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
            raise TypeError(f"UID storage returned an instance of {type(result).__name__} instead of {cls.__name__}.")
        return result


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

    def __del__(self):
        # No need to track deletion in finalizing state
        if sys.is_finalizing:
            return

        self.log.debug(f"Entity __del__ called for {self}.")

        if self.superseded:
            self.entity_log.on_delete(self, who='system', why='__del__')

    def is_newer_version_than(self, other : 'Entity') -> bool:
        if not isinstance(other, Entity):
            raise TypeError(f"Expected Entity, got {type(other)}")
        if self.uid != other.uid:
            raise ValueError(f"Cannot compare versions of entities with different UIDs: {self.uid} vs {other.uid}")
        return self.version > other.version

    @computed_field
    @property
    def superseded(self) -> bool:
        """
        Indicates whether this entity instance has been superseded by another instance with an incremented version.
        """
        return self.entity_log.version > self.version

    @property
    def superseding[T : 'Entity'](self : T) -> T | None:
        if not self.superseded:
            return self
        return self.__class__.by_uid(self.uid)

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
            target_name = self.reverse_field_alias(field_name)
            if field_name in kwargs:
                args[target_name] = kwargs[field_name]
            else:
                args[target_name] = getattr(self, field_name)

        args.update(kwargs)
        args['uid'    ] = self.uid
        args['version'] = self.entity_log.next_version

        # Sanity check - name won't change
        from .named_entity import NamedEntity
        is_named = False
        if isinstance(self, NamedEntity):
            if not isinstance(self, NamedProtocol):
                raise TypeError("Entity is a NamedEntity but not a NamedProtocol.")
            is_named = True
            if (new_name := self.calculate_instance_name_from_dict(args)) != self.instance_name:
                raise ValueError(f"Updating the entity cannot change its instance name. Original: '{self.instance_name}', New: '{new_name}'.")

        # Update entity
        print(args)
        new_entity = self.__class__(**args)

        # Sanity check - name didn't change
        if not isinstance(new_entity, self.__class__):
            raise TypeError(f"Expected new entity to be an instance of {self.__class__.__name__}, got {type(new_entity).__name__}.")
        if is_named:
            if not isinstance(new_entity, NamedProtocol) or not isinstance(self, NamedProtocol):
                raise TypeError("New entity or original entity is not a NamedProtocol but one was expected.")
            if new_entity.instance_name != self.instance_name:
                raise ValueError(f"Updating the entity cannot change its instance name. Original: '{self.instance_name}', New: '{new_entity.instance_name}'.")

        # Return updated entity
        return new_entity


    # MARK: Journal
    @property
    def journal(self) -> 'EntityJournal':
        result = self.session.get_entity_journal(entity=self)
        if result is None:
            raise RuntimeError("Entity does not have an associated journal.")
        return result

    def get_journal(self) -> 'EntityJournal | None':
        return self.session.get_entity_journal(entity=self)

    @cached_property
    def session_manager(self) -> 'SessionManager':
        parent = self.instance_parent

        from ...journal.session_manager import HasSessionManagerProtocol
        if not isinstance(parent, HasSessionManagerProtocol):
            raise RuntimeError(f"{self.__class__.__name__} is not part of a session-managed hierarchy (parent has type {parent.__class__}). Cannot determine session manager.")

        return parent.session_manager

    @property
    def session(self) -> 'JournalSession':
        session = self.session_manager.session
        if session is None:
            raise RuntimeError("No active session found in the session manager.")

        return session

    @staticmethod
    def _is_entity_attribute(name: str) -> bool:
        return hasattr(Entity, name) or name in Entity.model_fields or name in Entity.model_computed_fields

    @classmethod
    def is_model_field_alias(cls, alias : str) -> bool:
        return cls.model_field_aliases.get(alias, None) is not None

    @classmethod
    def resolve_field_alias(cls, alias : str) -> str:
        return cls.model_field_aliases.get(alias, alias)

    @classmethod
    def reverse_field_alias(cls, name : str) -> str:
        return cls.model_field_reverse_aliases.get(name, name)

    @classmethod
    def is_model_field(cls, field : str) -> bool:
        return field in cls.model_fields

    @classmethod
    def is_computed_field(cls, field : str) -> bool:
        return field in cls.model_computed_fields

    @property
    def original_instance_parent(self) -> Any:
        return super().__getattribute__('instance_parent')

    # Overriding __getattribute__ causes type checkers to assume any attribute access might succeed.
    # We don't plan to add/remove attributes, just proxy some of them to the journal.
    # So we gate our override with `not TYPE_CHECKING` to avoid confusing type checkers while keeping runtime behavior.
    if not TYPE_CHECKING:
        @override
        def __getattribute__(self, name: str) -> Any:
            # We special-case instance_parent to ensure we always link to the latest version of our parent entity
            if name == 'instance_parent':
                parent = super().__getattribute__(name)
                if isinstance(parent, Entity) and parent.superseded:
                    return parent.superseding
                return parent

            # Short-circuit cases
            if (
                # Short-circuit private and 'Entity' attributes
                (name.startswith('_') or Entity._is_entity_attribute(name)) or
                # Short-circuit if not yet initialized
                (not self.initialized) or
                # If this is not a model field
                (not self.is_model_field(name)) or
                # If not in a session, return the normal attribute
                (self.superseded or not self.in_session)
            ):
                return super().__getattribute__(name)

            # If there is no journal, return the normal attribute
            journal = self.get_journal()
            if journal is None:
                return super().__getattribute__(name)

            # Otherwise, use the journal to get the attribute
            return journal.get(name)

    @override
    def __setattr__(self, name: str, value: Any) -> None:
        if (
            # Short-circuit private and 'Entity' attributes
            (name.startswith('_') or Entity._is_entity_attribute(name)) or
            # Short-circuit if not yet initialized
            (not self.initialized) or
            # If this is not a model field
            (not self.is_model_field(name)) or
            # If not in a session, set the normal attribute
            (self.superseded or not self.in_session)
        ):
            return super().__setattr__(name, value)

        # If there is no journal, set the normal attribute
        journal = self.get_journal()
        if journal is None:
            return super().__setattr__(name, value)

        # Otherwise, use the journal to set the attribute
        journal.set(name, value)

    @property
    def dirty(self) -> bool:
        return self.journal.dirty

    @property
    def in_session(self) -> bool:
        try:
            manager = self.session_manager
        except:
            return False
        return manager.in_session


    # MARK: Utilities
    @override
    def __hash__(self):
        return hash((self.uid, self.version))