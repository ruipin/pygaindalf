# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import sys
import inspect

from frozendict import frozendict
from pydantic import ConfigDict, ValidationInfo, model_validator, Field, field_validator, computed_field, model_validator, PositiveInt, PositiveInt, PrivateAttr, BaseModel
from typing import override, Any, ClassVar, TYPE_CHECKING, Self, Iterable, cast as typing_cast, TypeVar, Callable
from abc import abstractmethod, ABCMeta
from collections.abc import Set, MutableSet
from functools import cached_property

from ....util.helpers.generics import GenericIntrospectionMixin
from ....util.mixins import NamedProtocol, NamedMixinMinimal
from ....util.models import LoggableHierarchicalModel
from ....util.helpers import script_info, generics
from ....util.callguard import CallguardClassOptions

if TYPE_CHECKING:
    from ...collections.uid_proxy import UidProxyFrozenSet
    from ...journal.entity_journal import EntityJournal
    from ...journal.session_manager import SessionManager
    from ...journal.session import Session
    from ..store.entity_store import EntityStore
    from ..annotation import Annotation
    from _typeshed import SupportsRichComparison

from ..uid import Uid

from .superseded import superseded_check
from .entity_audit_log import EntityAuditLog, EntityAuditType
from .entity_dependents import EntityDependents
from .dependency_event_handler import *
from .entity_base import EntityBase


ENTITY_SUBCLASSES = set()


class Entity[T_Journal : EntityJournal](LoggableHierarchicalModel, EntityBase, NamedMixinMinimal, metaclass=ABCMeta):
    __callguard_class_options__ = CallguardClassOptions['Entity'](
        decorator=superseded_check, decorate_public_methods=True,
        ignore_patterns=('superseding', 'superseded', 'deleted', 'marked_for_deletion', 'uid', 'version')
    )

    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        validate_assignment=True,
    )


    # MARK: Metaclass infrastructure
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        ENTITY_SUBCLASSES.add(cls)

        # Collect field aliases into a single collection
        aliases : dict[str,str] = dict()
        reverse : dict[str,str] = dict()

        for name, info in cls.model_fields.items():
            if info.alias:
                aliases[info.alias] = name
                reverse[name] = info.alias

        cls.model_field_aliases = frozendict(aliases)
        cls.model_field_reverse_aliases = frozendict(reverse)

        # Initialise dependencies
        cls.__init_dependencies__()

    @classmethod
    def is_update_allowed(cls, *, in_commit_only : bool = True, allow_in_abort : bool = False, force_session : bool = False) -> bool:
        # Check if we are in the middle of a commit
        from ...journal.session_manager import SessionManager
        session_manager = SessionManager.get_global_manager_or_none()
        if session_manager is None:
            if force_session or not script_info.is_unit_test():
                return False
        else:
            if not session_manager.in_session or (session := session_manager.session) is None:
                return False
            if allow_in_abort and session.in_abort:
                return True
            if in_commit_only and not session.in_commit:
                return False

        return True



    # MARK: Initialization / Destruction
    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        if not cls.is_update_allowed(in_commit_only=False):
            raise RuntimeError(f"Not allowed to create {cls.__name__} instances outside of a session.")
        return super().__new__(cls, *args, **kwargs)

    @override
    def model_post_init(self, context : Any) -> None:
        super().model_post_init(context)

        self.entity_log.on_init(self)
        self.entity_dependents.on_init(self)
        if self.entity_log.most_recent.what == EntityAuditType.CREATED and (session := self.session_or_none) is not None:
            session.on_entity_created(self)


    # MARK: Deletion
    _deleted : bool = PrivateAttr(default=False)

    def __del__(self):
        # No need to track deletion in finalizing state
        if sys.is_finalizing:
            return

        self.log.debug(t"Entity __del__ called for {self}.")
        if not self.superseded:
            self.log.warning(t"Entity {self} is being garbage collected without being superseded. This may indicate a logic error or improper session management.")
            self._apply_deletion(who='system', why='__del__')

    def delete(self) -> None:
        if self.marked_for_deletion:
            return

        if not self.is_update_allowed(in_commit_only=False):
            raise RuntimeError(f"Not allowed to delete {self.__class__.__name__} instances outside of a session.")

        self.log.debug(t"Entity delete called for {self}.")

        session = self.session_or_none
        if session is not None:
            session.mark_entity_for_deletion(self)
            self._propagate_deletion()
        else:
            self._apply_deletion()

    def _propagate_deletion(self) -> None:
        for uid in self.children_uids:
            child = Entity.by_uid_or_none(uid)
            if child is not None and not child.marked_for_deletion:
                child.delete()

    def apply_deletion(self, *, who : str | None = None, why : str | None = None) -> None:
        if not self.is_update_allowed(allow_in_abort=True):
            raise RuntimeError(f"Not allowed to apply deletion to {self.__class__.__name__} instances outside of a session commit.")

        self._apply_deletion(who=who, why=why)

    def _apply_deletion(self, *, who : str | None = None, why : str | None = None) -> None:
        try:
            if not self.marked_for_deletion:
                self._deleted = True
                self._propagate_deletion()
            else:
                self._deleted = True

            if not self.deletion_announced:
                self.announce_deletion()

            self.entity_log.on_delete(self, who=who, why=why)
            self.entity_dependents.on_delete(self)

            entity_store = self.__class__._get_entity_store()
            del entity_store[self.uid]
        except:
            self._deleted = False
            raise

    @property
    def marked_for_deletion(self) -> bool:
        if self._deleted:
            return True
        if self.superseded:
            return False
        session = self.session_or_none
        if session is not None and session.is_entity_marked_for_deletion(self):
            return True
        return False

    @property
    def deletion_announced(self) -> bool:
        if self._deleted:
            return True
        session = self.session_or_none
        if session is not None and session.has_entity_deletion_been_announced(self):
            return True
        return False

    @property
    def deleted(self) -> bool:
        return self._deleted

    def announce_deletion(self) -> None:
        if not self.is_update_allowed(allow_in_abort=True):
            raise RuntimeError(f"Not allowed to announce deletion of {self.__class__.__name__} instances outside of a session commit.")

        if self.deletion_announced:
            return

        for uid in self.dependent_uids:
            dep = Entity.by_uid_or_none(uid)
            if dep is None or dep.marked_for_deletion:
                continue
            dep.on_dependency_deleted(self)



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

        instance_name = instance_name.removeprefix(cls.uid_namespace())
        instance_name = instance_name.removeprefix('@')

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

        # If this entity already exists in the store, confirm a version was explicitly passed
        if (existing := cls._get_entity_store().get(uid, None)) is not None:
            version = data.get('version', None)
            if version is None:
                raise ValueError(f"Entity with UID {uid} already exists. You must provide an explicit version to create a new version of the entity.")
            elif version != existing.entity_log.next_version:
                raise ValueError(f"Entity with UID {uid} already exists with version {existing.version}. You must provide the next version {existing.entity_log.next_version} to create a new version of the entity.")

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
            raise ValueError(f"Global EntityStore is not set. Please create an EntityStore instance and call set_as_global_store() on it before creating {cls.__name__} instances.")
        return uid_storage

    @classmethod
    def by_uid_or_none[T : Entity](cls : type[T], uid: Uid) -> T | None:
        if not isinstance(uid, Uid):
            raise TypeError(f"Expected 'uid' to be of type Uid, got {type(uid).__name__}.")
        result = cls._get_entity_store().get(uid, None)
        if result is None:
            return None
        if not isinstance(result, cls):
            raise TypeError(f"UID storage returned an instance of {type(result).__name__} instead of {cls.__name__}.")
        return result

    @classmethod
    def by_uid[T : Entity](cls : type[T], uid: Uid) -> T:
        if (result := cls.by_uid_or_none(uid)) is None:
            raise ValueError(f"Could not find an entity of type {cls.__name__} for UID {uid}.")
        return result

    @classmethod
    def narrow_to_uid[T : Entity](cls : type[T], value : T | Uid) -> Uid:
        if isinstance(value, Uid):
            if inspect.isabstract(cls):
                # try to convert to concrete entity so we can test isinstance
                entity = cls.by_uid_or_none(value)
                if entity is None:
                    # We cannot sanity check in this case - we want to support narrowing UIDs that may not yet exist in the store
                    pass
                elif not isinstance(entity, cls):
                    raise TypeError(f"UID {value} does not correspond to an instance of abstract class {cls.__name__}. Found instance of {type(entity).__name__}.")
            elif not value.namespace != cls.uid_namespace():
                raise ValueError(f"UID namespace '{value.namespace}' does not match expected namespace '{cls.uid_namespace()}'.")
            return value
        elif isinstance(value, cls):
            return value.uid
        else:
            raise TypeError(f"Value must be a {cls.__name__} or Uid, got {type(value)}")

    @classmethod
    def narrow_to_entity_or_none[T : Entity](cls : type[T], value : T | Uid) -> T | None:
        if isinstance(value, cls):
            return value

        elif isinstance(value, Uid):
            entity = cls.by_uid(value)
            if entity is None:
                return None
            if not isinstance(entity, cls):
                raise TypeError(f"UID {value} does not correspond to an instance of {cls.__name__}. Found instance of {type(entity).__name__}.")
            return entity

        else:
            raise TypeError(f"Value must be a {cls.__name__} or Uid, got {type(value)}")

    @classmethod
    def narrow_to_entity[T : Entity](cls : type[T], value : T | Uid) -> T:
        if (result := cls.narrow_to_entity_or_none(value)) is None:
            raise ValueError(f"Could not find an entity of type {cls.__name__} for value {value}.")
        return result


    # MARK: Parent
    @property
    def entity_parent_or_none(self) -> Entity | None:
        parent = self.instance_parent
        if parent is None or not isinstance(parent, Entity):
            return None
        if parent.superseded:
            return None
        return parent

    @property
    def entity_parent(self) -> Entity:
        if (parent := self.entity_parent_or_none) is None:
            raise ValueError(f"{self.__class__.__name__} instance {self.uid} has no valid entity parent.")
        return parent


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
    def superseding_or_none[T : Entity](self : T) -> T | None:
        if not self.superseded:
            return self
        return self.__class__.by_uid_or_none(self.uid)

    @property
    def superseding[T : Entity](self : T) -> T:
        if (result := self.superseding_or_none) is None:
            raise ValueError(f"Entity {self} has been superseded but the superseding entity could not be found.")
        return result

    def update[T : Entity](self : T, **kwargs: Any) -> T:
        """
        Creates a new instance of the entity with the updated data.
        The new instance will have an incremented version and the same UID, superseding the current instance.
        """
        # Check if we are in the middle of a commit
        if not self.is_update_allowed():
            raise RuntimeError(f"Not allowed to update {self.__class__.__name__} instances outside of a session commit.")

        # Validate data
        if not kwargs:
            raise ValueError("No data provided to update the entity.")

        if 'uid' in kwargs:
            raise ValueError("Cannot update the 'uid' of an entity. The UID is immutable and should not be changed.")
        if 'version' in kwargs:
            raise ValueError("Cannot update the 'version' of an entity. The version is managed by the entity itself and should not be changed directly.")
        if 'entity_links' in kwargs:
            raise ValueError("Cannot update the 'entity_links' of an entity. The links are managed by the entity itself and should not be changed directly.")

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
    @property
    def session_manager_or_none(self) -> SessionManager | None:
        from ...journal.session_manager import SessionManager
        return SessionManager.get_global_manager_or_none()

    @property
    def session_manager(self) -> SessionManager:
        from ...journal.session_manager import SessionManager
        return SessionManager.get_global_manager()

    @property
    def session_or_none(self) -> Session | None:
        if (manager := self.session_manager_or_none) is None:
            return None
        return manager.session

    @property
    def session(self) -> Session:
        if (session := self.session_or_none) is None:
            raise RuntimeError("No active session found in the session manager.")
        return session

    get_journal_class = generics.GenericIntrospectionMethod[T_Journal]()

    def get_journal(self, *, create : bool = True, fail : bool = True) -> EntityJournal | None:
        session = self.session if fail else self.session_or_none
        return session.get_entity_journal(entity=self, create=create) if session is not None else None

    @property
    def journal_or_none(self) -> T_Journal | None:
        result = self.get_journal(create=True)
        if result is None:
            return None
        journal_cls = self.get_journal_class()
        if type(result) is not journal_cls:
            raise RuntimeError(f"Expected journal of type {journal_cls}, got {type(result)}.")
        return result

    @property
    def journal(self) -> T_Journal:
        if (result := self.journal_or_none) is None:
            raise RuntimeError(f"No journal found for entity {self}.")
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
    def dirty(self) -> bool:
        return self.journal.dirty

    @property
    def in_session(self) -> bool:
        try:
            manager = self.session_manager
        except:
            return False
        return manager.in_session



    # MARK: Children
    # These are all entities that are considered reachable (and therefore not garbage collected) by the existence of this entity.
    # I.e. those referenced by fields in the entity as well as annotations.
    def _get_children_field_ignore(self, field_name: str) -> bool:
        return field_name.startswith('_') or field_name in ('uid', 'extra_dependency_uids')

    def iter_children_uids(self, *, use_journal : bool = False) -> Iterable[Uid]:
        # Inspect all fields of the entity for UIDs or Entities
        for attr in self.__class__.model_fields.keys():
            if self._get_children_field_ignore(attr):
                continue

            if use_journal and (journal := self.get_journal(create=False)) is not None and journal.is_field_edited(attr):
                value = getattr(journal, attr, None)
            else:
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

    @cached_property
    def children_uids(self) -> Iterable[Uid]:
        return frozenset(self.iter_children_uids())

    @property
    def journal_children_uids(self) -> Iterable[Uid]:
        journal = self.get_journal(create=False)
        return self.children_uids if journal is None else journal.children_uids

    @property
    def children(self) -> Iterable[Entity]:
        for uid in self.children_uids:
            yield Entity.by_uid(uid)

    def iter_hierarchy(self, *, condition : Callable[[Entity], bool] | None = None, check_condition_on_return : bool = True) -> Iterable[Entity]:
        """
        Return a flat ordered set of all entities in this hierarchy
        """
        if condition is not None and not condition(self):
            return

        # Iterate dirty children journals
        for uid in self.children_uids:
            child = Entity.by_uid_or_none(uid)
            if child is None:
                continue

            if condition is not None and not condition(child):
                continue

            yield from child.iter_hierarchy(condition=condition)

        if check_condition_on_return and condition is not None and not condition(self):
            raise RuntimeError(f"Entity {self} failed condition check on return of yield_hierarchy.")

        # Yield self, then return
        yield self

    def is_reachable(self, *, use_journal : bool = False) -> bool:
        from ..root import EntityRoot
        parent = self.instance_parent
        if parent is None:
            raise ValueError(f"Entity {self} has no parent, cannot determine reachability.")
        if isinstance(parent, EntityRoot):
            return True
        if not isinstance(parent, Entity):
            raise TypeError(f"Entity {self} has a parent of type {type(parent).__name__}, expected Entity or EntityRoot.")

        # Check if parent contains us
        iterable = parent.children_uids if not use_journal else parent.journal_children_uids
        if self.uid not in iterable:
            return False

        # Recurse up the tree
        return parent.is_reachable(use_journal=use_journal)



    # MARK: Annotations
    annotation_uids : frozenset[Uid] = Field(default_factory=frozenset, description="The UIDs of annotations associated with this entity.")

    @property
    def annotations(self) -> UidProxyFrozenSet[Entity]:
        from ...collections.uid_proxy import UidProxyFrozenSet
        return UidProxyFrozenSet[Entity](owner=self, field='annotation_uids')

    def on_annotation_created(self, annotation_or_uid : Annotation | Uid) -> None:
        if not self.is_update_allowed(in_commit_only=False, force_session=True):
            raise RuntimeError(f"Not allowed to modify annotations of {self.__class__.__name__} instances outside of a session.")

        from ..annotation import Annotation
        uid = Annotation.narrow_to_uid(annotation_or_uid)
        if uid in self.journal.annotation_uids:
            return

        self.journal.annotation_uids.add(uid)

    def on_annotation_deleted(self, annotation_or_uid : Annotation | Uid) -> None:
        self.log.debug(t"Entity {self} received deletion notice for annotation {annotation_or_uid}.")

        if not self.is_update_allowed(in_commit_only=False, force_session=True):
            raise RuntimeError(f"Not allowed to modify annotations of {self.__class__.__name__} instances outside of a session.")

        from ..annotation import Annotation
        uid = Annotation.narrow_to_uid(annotation_or_uid)
        if uid not in self.journal.annotation_uids:
            return

        self.journal.annotation_uids.discard(uid)


    # MARK: Dependents
    entity_dependents : EntityDependents = Field(default_factory=lambda data: EntityDependents(data['uid']), validate_default=True, repr=False, exclude=True, description="The dependents of this entity, which tracks other entities that depend on this entity.")

    @property
    def dependent_uids(self) -> Iterable[Uid]:
        return self.entity_dependents.dependent_uids

    @property
    def dependents(self) -> Iterable[Entity]:
        return self.entity_dependents.dependents


    # MARK: Dependencies
    extra_dependency_uids : frozenset[Uid] = Field(default_factory=frozenset, exclude=True, repr=False, json_schema_extra={'propagate': False}, description="Extra dependency UIDs. These can be used to create dependencies in addition to those automatically tracked by the entity.")

    @property
    def extra_dependencies(self) -> UidProxyFrozenSet[Entity]:
        from ...collections.uid_proxy import UidProxyFrozenSet
        return UidProxyFrozenSet[Entity](owner=self, field='extra_dependency_uids')


    # MARK: Dependency Events
    __entity_dependency_event_handler_records__ : ClassVar[MutableSet[EntityDependencyEventHandlerRecord]]

    @classmethod
    def __init_dependencies__(cls) -> None:
        cls.__entity_dependency_event_handler_records__ = set()

    @classmethod
    def register_dependency_event_handler(cls, record : EntityDependencyEventHandlerRecord) -> None:
        cls.__entity_dependency_event_handler_records__.add(record)

    if script_info.is_unit_test():
        @classmethod
        def clear_dependency_event_handlers(cls) -> None:
            if hasattr(cls, '__entity_dependency_event_handler_records__'):
                cls.__entity_dependency_event_handler_records__.clear()
                cls.__init_dependencies__()

            for t in ENTITY_SUBCLASSES:
                if issubclass(t, cls):
                    if hasattr(t, '__entity_dependency_event_handler_records__'):
                        t.__entity_dependency_event_handler_records__.clear()
                        t.__init_dependencies__()

    @classmethod
    def iter_dependency_event_handlers(cls) -> Iterable[EntityDependencyEventHandlerRecord]:
        for subclass in cls.__mro__:
            if not issubclass(subclass, Entity):
                continue
            if not hasattr(subclass, '__entity_dependency_event_handler_records__'):
                continue
            for record in subclass.__entity_dependency_event_handler_records__:
                yield record

    @overload
    def _call_dependency_event_handlers(self, event : Literal[EntityDependencyEventType.INVALIDATED], entity : Entity, journal : EntityJournal) -> bool: ...
    @overload
    def _call_dependency_event_handlers(self, event : Literal[EntityDependencyEventType.DELETED], entity : Entity, journal : None = None) -> bool: ...
    def _call_dependency_event_handlers(self, event : EntityDependencyEventType, entity : Entity, journal : EntityJournal | None = None) -> bool:
        matched = False
        for record in self.__class__.iter_dependency_event_handlers():
            if event is EntityDependencyEventType.DELETED:
                assert journal is None
                matched_current = record(owner=self, event=event, entity=entity)
            elif event is EntityDependencyEventType.INVALIDATED:
                assert journal is not None
                matched_current = record(owner=self, event=event, entity=entity, journal=journal)
            else:
                raise ValueError(f"Unknown event type: {event}")

            matched |= matched_current

            # Abort if one of the handlers marks this entity for deletion
            if matched_current and self.marked_for_deletion:
                break
        return matched

    def on_dependency_invalidated(self, source: EntityJournal) -> None:
        entity = source.entity

        self.log.debug(t"Entity {self} received invalidation from dependency entity {entity}.")

        # TODO: It should be possible to do this without creating a journal unless strictly necessary
        self.journal.on_dependency_invalidated(source)

        # Call event handlers
        self._call_dependency_event_handlers(event=EntityDependencyEventType.INVALIDATED, entity=entity, journal=source)

    def on_dependency_deleted(self, entity: Entity) -> None:
        self.log.debug(t"Entity {self} received deletion notice from dependency entity {entity}.")

        # If the entity is the parent of this entity, then we should delete ourselves too
        if (parent := self.entity_parent_or_none) is not None and parent.uid == entity.uid:
            self.log.warning(t"Entity {self} is a child of deleted entity {entity}, deleting itself too.")
            self.delete()
            return

        # Sanity check: Entity cannot be the parent of this entity
        if entity is self.entity_parent_or_none:
            raise RuntimeError(f"Entity {entity} is the parent of {self} and cannot be deleted without deleting the child first.")

        # Sanity check: Entity cannot be a child of this entity
        if entity.uid in self.journal_children_uids:
            if self.is_reachable(use_journal=True):
                raise RuntimeError(f"Entity {entity} is a child of {self} and cannot be deleted.")
            else:
                # TODO: As part of _propagate_delete, entities should try to remove themselves from their parent. This is hack here to handle the situation where they don't.
                self.log.warning(t"Entity {self} is no longer reachable, but is not deleted. Marking for deletion.")
                self.delete()
                return

        # Call event handlers
        self._call_dependency_event_handlers(event=EntityDependencyEventType.DELETED, entity=entity)
        if self.marked_for_deletion:
            return

        # If the entity is in our extra dependencies, we remove it
        if entity.uid in self.extra_dependency_uids:
            self.journal.remove_dependency(entity.uid)




    # MARK: Utilities
    def sort_key(self) -> SupportsRichComparison:
        return self.uid

    @override
    def __hash__(self):
        return hash((self.uid, self.version))

    @override
    def __str__(self) -> str:
        version = getattr(self, 'version', '?')
        return super().__str__().replace('>', f" v{version}>")

    @override
    def __repr__(self) -> str:
        version = getattr(self, 'version', '?')
        return super().__repr__().replace('>', f" v{version}>")