# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import sys
import inspect

from frozendict import frozendict
from pydantic import ConfigDict, ValidationInfo, model_validator, Field, field_validator, computed_field, model_validator, PositiveInt, PositiveInt, PrivateAttr, BaseModel
from typing import override, Any, ClassVar, TYPE_CHECKING, Self, Iterable, cast as typing_cast
from abc import abstractmethod, ABCMeta
from collections.abc import Set, MutableSet
from functools import cached_property

from ....util.mixins import NamedProtocol, NamedMixinMinimal
from ....util.models import LoggableHierarchicalModel
from ....util.helpers import script_info
from ....util.callguard import CallguardClassOptions

if TYPE_CHECKING:
    from ...journal.entity_journal import EntityJournal
    from ...journal.session_manager import SessionManager
    from ...journal.session import Session
    from ..store.entity_store import EntityStore
    from ..annotation import Annotation
    from _typeshed import SupportsRichComparison

from ..uid import Uid

from .superseded import superseded_check
from .entity_audit_log import EntityAuditLog, EntityAuditType


class Entity[T_Journal : 'EntityJournal'](LoggableHierarchicalModel, NamedMixinMinimal, metaclass=ABCMeta):
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

    @classmethod
    def is_update_allowed(cls, *, in_commit_only : bool = True, allow_in_abort : bool = False) -> bool:
        # Check if we are in the middle of a commit
        from ...journal.session_manager import SessionManager
        session_manager = SessionManager.get_global_manager_or_none()
        if session_manager is None:
            if not script_info.is_unit_test():
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

        self.entity_log.on_create(self)
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
        if self._deleted:
            return

        if not self.is_update_allowed(in_commit_only=False):
            raise RuntimeError(f"Not allowed to delete {self.__class__.__name__} instances outside of a session.")

        self._deleted = True
        self._propagate_deletion()

        session = self.session_or_none
        if session is None:
            self._apply_deletion()
        else:
            self.session.mark_entity_for_deletion(self)

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
        if not self._deleted:
            self._propagate_deletion()
        self._deleted = True

        self.entity_log.on_delete(self, who=who, why=why)
        self._announce_deletion()

        entity_store = self.__class__._get_entity_store()
        del entity_store[self.uid]

    @property
    def marked_for_deletion(self) -> bool:
        return self._deleted

    def _announce_deletion(self) -> None:
        if not self.is_update_allowed(allow_in_abort=True):
            raise RuntimeError(f"Not allowed to announce deletion of {self.__class__.__name__} instances outside of a session commit.")

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
        return parent

    @property
    def entity_parent(self) -> Entity:
        if (parent := self.entity_parent_or_none) is None:
            raise ValueError(f"{self.__class__.__name__} instance {self} has no valid entity parent.")
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
    def superseding[T : Entity](self : T) -> T | None:
        if not self.superseded:
            return self
        return self.__class__.by_uid_or_none(self.uid)

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

    @classmethod
    def get_journal_class(cls) -> type[T_Journal]:
        from ...journal import EntityJournal
        return typing_cast(type[T_Journal], EntityJournal)

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
    def _get_children_uids(self) -> Iterable[Uid]:
        # Inspect all fields of the entity for UIDs or Entities
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

        # Annotations are also considered children
        yield from self.annotation_uids

    @cached_property
    def children_uids(self) -> Iterable[Uid]:
        return frozenset(self._get_children_uids())

    @property
    def children(self) -> Iterable[Entity]:
        for uid in self.children_uids:
            yield Entity.by_uid(uid)

    def _reset_children_cache(self) -> None:
        try:
            del self.__dict__['children_uids']
        except KeyError:
            pass


    # MARK: Annotations
    _annotation_uids : MutableSet[Uid] = PrivateAttr(default_factory=set)

    @computed_field(description="The UIDs of annotations associated with this entity.")
    @property
    def annotation_uids(self) -> Iterable[Uid]:
        yield from self._annotation_uids

    def get_annotations[T : Annotation](self, cls : type[T]) -> Iterable[T]:
        from ..annotation import Annotation
        for uid in self.annotation_uids:
            annotation = Annotation.narrow_to_entity(uid)
            if not isinstance(annotation, cls):
                continue
            yield annotation

    def get_annotation_uids(self, cls : type[Annotation]) -> Iterable[Uid]:
        for annotation in self.get_annotations(cls):
            yield annotation.uid

    @property
    def annotations(self) -> Iterable[Annotation]:
        from ..annotation import Annotation
        yield from self.get_annotations(Annotation)

    def on_annotation_created(self, annotation_or_uid : Annotation | Uid) -> None:
        from ..annotation import Annotation
        annotation = Annotation.narrow_to_entity(annotation_or_uid)
        if annotation.uid in self._annotation_uids:
            return

        self._annotation_uids.add(annotation.uid)
        self._reset_children_cache()

    def on_annotation_deleted(self, annotation_or_uid : Annotation | Uid) -> None:
        from ..annotation import Annotation
        annotation = Annotation.narrow_to_entity(annotation_or_uid)
        if annotation.uid not in self._annotation_uids:
            return

        self._annotation_uids.remove(annotation.uid)
        self._reset_children_cache()


    # MARK: Links
    #_manual_dependent_uids : Set[Uid] = PrivateAttr(default_factory=frozenset)
    #_manual_dependency_uids : Set[Uid] = PrivateAttr(default_factory=frozenset)

    @property
    def dependent_uids(self) -> Iterable[Uid]:
        parent = self.entity_parent_or_none
        if parent is not None:
            yield parent.uid

        yield from self.children_uids
        #yield from self._manual_dependent_uids

    @property
    def dependents(self) -> Iterable[Entity]:
        for uid in self.dependent_uids:
            yield uid.entity

    #@property
    #def _manual_dependencies(self) -> Iterable[Entity]:
    #    for uid in self._manual_dependency_uids:
    #        entity = Entity.by_uid(uid)
    #        if entity is None:
    #            raise RuntimeError(f"Dependency entity with UID {uid} not found in store.")
    #        yield entity


    def on_dependency_invalidated(self, source: EntityJournal) -> None:
        self.log.debug(t"Entity {self} received invalidation from dependency entity {source.entity}.")
        self.journal.on_dependency_invalidated(source)

    def on_dependency_deleted(self, entity: Entity) -> None:
        self.log.debug(t"Entity {self} received deletion notice from dependency entity {entity}.")

        # If the entity is the parent of this entity, then we should delete ourselves too
        if (parent := self.entity_parent_or_none) is not None and parent.uid == entity.uid:
            self.log.debug(t"Entity {self} is a child of deleted entity {entity}, deleting itself too.")
            self.delete()
            return

        # If the entity is an annotation of this entity, we need to delete it from our annotations set
        from ..annotation import Annotation
        if isinstance(entity, Annotation) and entity.uid in self._annotation_uids:
            self.log.debug(t"Entity {self} has annotation {entity} deleted, removing annotation.")
            self.on_annotation_deleted(entity)
            return

        # Sanity check: Entity cannot be the parent of this entity
        if entity is self.entity_parent_or_none:
            raise RuntimeError(f"Entity {entity} is the parent of {self} and cannot be deleted without deleting the child first.")

        # Sanity check: Entity cannot be a child of this entity
        if entity.uid in self.children_uids:
            raise RuntimeError(f"Entity {entity} is a child of {self} and cannot be deleted.")

        # Delete dependency link
        #self._manual_dependency_uids.discard(entity.uid)




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