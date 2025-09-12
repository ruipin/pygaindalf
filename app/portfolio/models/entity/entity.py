# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import sys
import functools

from frozendict import frozendict
from pydantic import BaseModel, ConfigDict, ModelWrapValidatorHandler, ValidationInfo, model_validator, Field, field_validator, computed_field, model_validator, PositiveInt, PositiveInt, PrivateAttr
from typing import override, Any, ClassVar, MutableMapping, TYPE_CHECKING, ContextManager, Self, Unpack, cast as typing_cast, Iterator, Iterable
from abc import abstractmethod, ABCMeta
from weakref import WeakValueDictionary
from functools import cached_property

from ....util.mixins import LoggableHierarchicalModel, NamedProtocol, NamedMixinMinimal
from ....util.helpers import script_info, generics
from ....util.callguard import CallguardClassOptions

if TYPE_CHECKING:
    from ...journal.entity_journal import EntityJournal
    from ...journal.session_manager import SessionManager
    from ...journal.session import JournalSession
    from ..store.entity_store import EntityStore
    from _typeshed import SupportsRichComparison

from ..uid import Uid

from .superseded import superseded_check
from .entity_audit_log import EntityAuditLog


class Entity[T_Journal : 'EntityJournal'](LoggableHierarchicalModel, NamedMixinMinimal):
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


    # MARK: Instance Name
    PROPAGATE_INSTANCE_NAME_FROM_PARENT : ClassVar[bool] = False
    STRICT_INSTANCE_NAME_VALIDATION : ClassVar[bool] = True

    @classmethod
    @abstractmethod
    def calculate_instance_name_from_dict(cls, data : dict[str, Any]) -> str:
        raise NotImplementedError(f"{cls.__name__} must implement the 'calculate_instance_name_from_dict' method to generate a name for the instance.")

    @classmethod
    def calculate_instance_name_from_instance(cls, instance : Entity) -> str:
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

    @computed_field(description="The instance name, or class name if not set.")
    @property
    def instance_name(self) -> str:
        """
        Get the instance name, or class name if not set.
        """
        return self.calculate_instance_name_from_dict(self.__dict__)



    # MARK: Uid
    # TODO: These should all be marked Final, but pydantic is broken here, see https://github.com/pydantic/pydantic/issues/10474#issuecomment-2478666651
    uid : Uid = Field(default_factory=lambda: None, validate_default=True, description="Unique identifier for the entity.") # pyright: ignore[reportAssignmentType] as the default value is overridden by _validate_uid_before anyway

    @classmethod
    def uid_namespace(cls) -> str:
        """
        Returns the namespace for the UID.
        This can be overridden in subclasses to provide a custom namespace.
        """
        return cls.__name__

    @classmethod
    def _calculate_uid(cls, data : dict[str, Any]) -> Uid:
        instance_name = cls.calculate_instance_name_from_dict(data)
        if instance_name is None:
            raise ValueError(f"{cls.__name__} must have an instance name when calculating its UID.")

        return Uid(namespace=cls.uid_namespace(), id=instance_name)

    @model_validator(mode='before')
    @classmethod
    def _validate_uid_before(cls, data: Any, info: ValidationInfo) -> Self:
        if (uid := data.get('uid', None)) is None:
            uid = {}

        if not isinstance(uid, Uid):
            uid = cls._calculate_uid(data)

        if not isinstance(uid, Uid):
            raise TypeError(f"Expected 'uid' to be of type Uid, got {type(uid).__name__}.")

        uid_namespace = cls.uid_namespace()
        if uid.namespace != uid_namespace:
            raise ValueError(f"Uid namespace '{uid.namespace}' does not match expected namespace '{uid_namespace}'.")

        data['uid'] = uid
        return data

    @model_validator(mode='after')
    def _validate_uid_after(self, info: ValidationInfo) -> Self:
        # Get a reference to the UID storage
        entity_store = self.__class__._get_entity_store()

        # If the entity already exists, we fail unless we are cloning the entity and incrementing the version
        existing = entity_store.get(self.uid, None)
        if existing and existing is not self:
            if (self.version <= existing.version):
                raise ValueError(f"Duplicate UID detected: {self.uid} with versions {self.version} vs {existing.version}. Each entity must have a unique UID or increment the version.")

        # Store the entity in the UID storage
        entity_store[self.uid] = self

        return self

    @classmethod
    def _get_entity_store(cls) -> EntityStore:
        from ..store.entity_store import EntityStore
        if (uid_storage := EntityStore.get_global_store()) is None:
            raise ValueError(f"{cls.__name__} must have a valid UID storage. The UID_STORAGE class variable cannot be None.")
        return uid_storage

    @classmethod
    def by_uid[T : Entity](cls : type[T], uid: Uid) -> T | None:
        result = cls._get_entity_store().get(uid, None)
        if result is None:
            return None
        if not isinstance(result, cls):
            raise TypeError(f"UID storage returned an instance of {type(result).__name__} instead of {cls.__name__}.")
        return result

    @classmethod
    def narrow_to_uid[T : Entity](cls : type[T], value : T | Uid) -> Uid:
        if isinstance(value, Uid):
            return value
        elif isinstance(value, cls):
            return value.uid
        else:
            raise TypeError(f"Value must be a {cls.__name__} or Uid, got {type(value)}")

    def get_child_uids(self) -> Iterable[Uid]:
        for attr in self.__class__.model_fields.keys():
            value = getattr(self, attr, None)
            if value is None:
                continue

            if isinstance(value, Uid):
                yield value
            elif isinstance(value, Entity):
                yield value.uid
            elif isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
                for item in value:
                    if isinstance(item, Uid):
                        yield item
                    elif isinstance(item, Entity):
                        yield item.uid


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

        self.log.debug(t"Entity __del__ called for {self}.")

        if self.superseded:
            self.entity_log.on_delete(self, who='system', why='__del__')

    def is_newer_version_than(self, other : Entity) -> bool:
        if not isinstance(other, Entity):
            raise TypeError(f"Expected Entity, got {type(other)}")
        if self.uid != other.uid:
            raise ValueError(f"Cannot compare versions of entities with different UIDs: {self.uid} vs {other.uid}")
        return self.version > other.version

    @computed_field(description="Indicates whether this entity instance has been superseded by another instance with an incremented version.")
    @property
    def superseded(self) -> bool:
        """
        Indicates whether this entity instance has been superseded by another instance with an incremented version.
        """
        return self.entity_log.version > self.version

    @property
    def superseding[T : Entity](self : T) -> T | None:
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
        if (new_name := self.calculate_instance_name_from_dict(args)) != self.instance_name:
            raise ValueError(f"Updating the entity cannot change its instance name. Original: '{self.instance_name}', New: '{new_name}'.")

        # Update entity
        new_entity = self.__class__(**args)

        # Sanity check - name didn't change
        if not isinstance(new_entity, self.__class__):
            raise TypeError(f"Expected new entity to be an instance of {self.__class__.__name__}, got {type(new_entity).__name__}.")
        if new_entity.instance_name != self.instance_name:
            raise ValueError(f"Updating the entity cannot change its instance name. Original: '{self.instance_name}', New: '{new_entity.instance_name}'.")

        # Return updated entity
        return new_entity


    # MARK: Session / Journal
    @cached_property
    def session_manager_or_none(self) -> SessionManager | None:
        parent = self.instance_parent

        from ...journal.session_manager import HasSessionManagerProtocol
        if not isinstance(parent, HasSessionManagerProtocol):
            return None

        return parent.session_manager

    @cached_property
    def session_manager(self) -> SessionManager:
        session_manager = self.session_manager_or_none
        if session_manager is None:
            raise RuntimeError(f"{self!r} is not part of a session-managed hierarchy, cannot determine session manager.")
        return session_manager

    @property
    def session_or_none(self) -> JournalSession | None:
        manager = self.session_manager_or_none
        return manager.session if manager is not None else None

    @property
    def session(self) -> JournalSession:
        session = self.session_manager.session
        if session is None:
            raise RuntimeError("No active session found in the session manager.")
        return session

    @classmethod
    def get_journal_class(cls) -> type[T_Journal]:
        raise NotImplementedError(f"{cls.__name__} must implement the 'get_journal_class' method to return the associated journal class.")

    def get_journal(self, *, create : bool = True, fail : bool = True) -> EntityJournal | None:
        session = self.session if fail else self.session_or_none
        return session.get_entity_journal(entity=self, create=create) if session is not None else None

    @property
    def journal(self) -> T_Journal:
        result = self.get_journal(create=True)
        if result is None:
            raise RuntimeError("Entity does not have an associated journal.")
        journal_cls = self.get_journal_class()
        if not isinstance(result, journal_cls):
            raise RuntimeError(f"Expected journal of type {journal_cls}, got {type(result)}.")
        return result

    @property
    def has_journal(self) -> bool:
        return self.get_journal(create=False) is not None


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



    # MARK: Subscriptions
    @property
    def dependents(self) -> Iterable[Uid]:
        # Parent is always a dependent
        parent = self.instance_parent
        if isinstance(parent, Entity):
            yield parent.uid

        # Yield all subscribers
        yield from self.entity_log.dependents

    def add_dependent(self, entity: Entity | Uid) -> None:
        uid = Entity.narrow_to_uid(entity)
        self.entity_log.add_dependent(uid)

    def remove_dependent(self, entity: Entity | Uid) -> None:
        uid = Entity.narrow_to_uid(entity)
        self.entity_log.remove_dependent(uid)

    @property
    def dependencies(self) -> Iterable[Uid]:
        yield from self.entity_log.dependencies

    def _add_dependency(self, entity: Entity | Uid) -> None:
        if isinstance(entity, Uid):
            entity_or_none = Entity.by_uid(entity)
            if entity_or_none is None:
                raise ValueError(f"Cannot add entity with UID {entity} as dependency, entity not found.")
            entity = entity_or_none

        entity.add_dependent(self)

    def _remove_dependency(self, entity: Entity | Uid) -> None:
        if isinstance(entity, Uid):
            entity_or_none = Entity.by_uid(entity)
            if entity_or_none is None:
                raise ValueError(f"Cannot remove entity with UID {entity} as dependency, entity not found.")
            entity = entity_or_none

        entity.remove_dependent(self)

    def on_dependency_invalidated(self, source: EntityJournal) -> None:
        self.log.debug(t"Entity {self} received invalidation from dependency entity {source.entity}.")

        self.journal.on_dependency_invalidated(source)



    # MARK: Utilities
    def sort_key(self) -> SupportsRichComparison:
        return self.uid

    @override
    def __hash__(self):
        return hash((self.uid, self.version))

    @override
    def __str__(self) -> str:
        return super().__str__().replace('>', f" v{self.version}>")

    @override
    def __repr__(self) -> str:
        return super().__repr__().replace('>', f" v{self.version}>")