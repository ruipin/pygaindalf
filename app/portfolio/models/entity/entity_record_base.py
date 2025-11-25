# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import sys

from abc import ABCMeta
from collections.abc import Iterable, MutableMapping, MutableSet
from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, Any, ClassVar, Self, override
from typing import cast as typing_cast

from frozendict import frozendict
from pydantic import ConfigDict, PositiveInt, PrivateAttr, ValidationInfo, field_serializer, field_validator, model_validator

from ....util.callguard import CallguardClassOptions
from ....util.helpers import generics, script_info, type_hints
from ....util.mixins import HierarchicalMixinMinimal, HierarchicalProtocol, NamedMixinMinimal, NamedProtocol
from ....util.models import LoggableHierarchicalRootModel
from ....util.models.superseded import superseded_check
from ....util.models.uid import Uid
from .dependency_event_handler.base import EntityDependencyEventHandlerBase
from .dependency_event_handler.type_enum import EntityDependencyEventType
from .entity_common import EntityCommon
from .entity_dependents import EntityDependents
from .entity_impl import EntityImpl
from .entity_log import EntityLog, EntityModificationType
from .entity_schema import EntitySchema


if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison

    from ...collections.uid_proxy import UidProxySet
    from ...journal.journal import Journal
    from ..store.entity_store import EntityStore
    from .entity import Entity


ENTITY_RECORD_SUBCLASSES: MutableSet[type[EntityRecordBase]] = set()
ENTITY_CLASSES: MutableMapping[type[EntityRecordBase], type[Entity]] = {}


# We need this class to swallow the 'init' kwarg in __init_subclass__ calls from EntityRecordBase
class EntityRecordMeta(metaclass=ABCMeta):
    def __init_subclass__(cls, *, init: bool = False) -> None:
        super().__init_subclass__()


class EntityRecordBase[
    T_Journal: Journal,
](
    EntityRecordMeta,
    type_hints.CachedTypeHintsMixin,
    LoggableHierarchicalRootModel,
    EntityImpl,
    EntityCommon[T_Journal],
    EntitySchema,
    NamedMixinMinimal,
    metaclass=ABCMeta,
    # We need init=False here to ensure that pyright looks at the __init__ method for the entity-specific EntitySchema base,
    # e.g. InstrumentSchema, TransactionSchema, etc
    init=False,
):
    __callguard_class_options__ = CallguardClassOptions["EntityRecordBase"](
        decorator=superseded_check,
        decorate_public_methods=True,
        ignore_patterns=(
            "superseding",
            "superseded",
            "deleted",
            "reverted",
            "exists",
            "marked_for_deletion",
            "uid",
            "version",
            "entity_or_none",
            "entity",
            "entity_log",
            "instance_name",
        ),
    )

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )

    # MARK: Metaclass infrastructure
    def __init_subclass__(cls, *, init: bool = False, unsafe_hash: bool = False) -> None:
        super().__init_subclass__()

        ENTITY_RECORD_SUBCLASSES.add(cls)

        # Initialise dependencies
        cls.__init_dependencies__()

    # MARK: Initialization / Destruction
    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        cls.assert_update_allowed(in_commit_only=False, force_session=False)
        return super().__new__(cls, *args, **kwargs)

    @override
    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)

        from .entity_record import EntityRecord

        assert isinstance(self, EntityRecord), f"Expected EntityRecord, got {type(self).__name__}"

        self.entity_log.on_init_record(self)
        self.entity_dependents.on_init_record(self)
        self.entity.on_init_record(self)
        if self.entity_log.most_recent.what == EntityModificationType.CREATED and (session := self.session_or_none) is not None:
            session.on_entity_record_created(self)

    # MARK: Deletion
    @property
    def deleted(self) -> bool:
        if not self.superseded:
            return False

        if self.reverted:
            return True

        superseding_log = self.entity_log.get_entry_by_version(self.version + 1)
        if superseding_log is None:
            msg = f"Entity record {self} is marked as superseded but no audit log entry found for version {self.version + 1}."
            raise ValueError(msg)

        return superseding_log.record_deleted

    @property
    def exists(self) -> bool:
        return not self.deleted

    @property
    def marked_for_deletion(self) -> bool:
        if self.deleted:
            return True

        journal = self.journal_or_none
        return journal.marked_for_deletion if journal is not None else False

    def __del__(self) -> None:
        # No need to track deletion in finalizing state
        if sys.is_finalizing:
            return

        self.log.debug(t"Entity record __del__ called for {self}.")
        if not self.superseded:
            self.log.warning(
                t"Entity record {self} is being garbage collected without being superseded. This may indicate a logic error or improper session management."
            )
            self._apply_deletion(who="system", why="__del__")

    def delete(self) -> None:
        if self.marked_for_deletion:
            return

        self.assert_update_allowed(in_commit_only=False, force_session=False)
        self.log.debug(t"Entity record delete called for {self}.")

        if self.in_session:
            self.journal.delete()
        else:
            assert script_info.is_unit_test(), f"Unexpected non-session deletion of {self} outside of unit test."
            self._apply_deletion()

    def propagate_deletion(self) -> None:
        if not self.marked_for_deletion:
            return

        for uid in self.children_uids:
            child = EntityRecordBase.by_uid_or_none(uid)
            if child is not None and not child.marked_for_deletion:
                child.delete()

    def apply_deletion(self, *, who: str | None = None, why: str | None = None) -> None:
        self.assert_update_allowed(allow_frozen_journal=True, allow_in_abort=True)

        self._apply_deletion(who=who, why=why)

    def _apply_deletion(self, *, who: str | None = None, why: str | None = None) -> None:
        from .entity_record import EntityRecord

        assert isinstance(self, EntityRecord), f"Expected EntityRecord, got {type(self).__name__}"

        self.entity_log.on_delete_record(self, who=who, why=why)
        self.entity_dependents.on_delete_record(self)

        self.entity.on_delete_record()

        self.log.info(t"Entity record {self} has been deleted.")

    # MARK: Revertion
    _reverted: bool = PrivateAttr(default=False)

    @property
    def reverted(self) -> bool:
        return getattr(self, "_reverted", False)

    def revert(self) -> None:
        if self.reverted:
            return

        self.assert_update_allowed(allow_in_abort=True)

        if self.entity_log.version >= self.version:
            msg = f"Cannot revert entity record {self} because its entity log is still tracking it."
            raise RuntimeError(msg)

        self._reverted = True

    # MARK: Instance Name
    PROPAGATE_INSTANCE_NAME_FROM_PARENT: ClassVar[bool] = False
    STRICT_INSTANCE_NAME_VALIDATION: ClassVar[bool] = True

    @property
    @override
    def instance_name(self) -> str:
        """Get the instance name, or class name if not set."""
        if (entity := self.entity_or_none) is None:
            return f"{type(self).__name__}@unknown"
        return entity.instance_name

    # MARK: Uid
    @model_validator(mode="before")
    @classmethod
    def _validate_uid_before(cls, data: Any) -> Self:
        if (uid := data.get("uid", None)) is None:
            msg = "Entity record must have a valid 'uid' to be created. None found."
            raise ValueError(msg)

        if not isinstance(uid, Uid):
            msg = f"Expected 'uid' to be of type Uid, got {type(uid).__name__}."
            raise TypeError(msg)

        if not isinstance(uid, Uid):
            msg = f"Expected 'uid' to be of type Uid, got {type(uid).__name__}."
            raise TypeError(msg)

        uid_namespace = cls.get_entity_class().uid_namespace()
        if uid.namespace != uid_namespace:
            msg = f"Uid namespace '{uid.namespace}' does not match expected namespace '{uid_namespace}'."
            raise ValueError(msg)

        # If this entity already exists in the store, confirm a version was explicitly passed
        if (existing := cls._get_entity_store().get_entity_record(uid)) is not None:
            version = data.get("version", None)
            if version is None:
                msg = f"Entity record with UID {uid} already exists. You must provide an explicit version to create a new version of the entity."
                raise ValueError(msg)
            elif version != existing.entity_log.next_version:
                msg = f"Entity record with UID {uid} already exists with version {existing.version}. You must provide the next version {existing.entity_log.next_version} to create a new version of the entity."
                raise ValueError(msg)

        data["uid"] = uid
        return data

    @classmethod
    def _get_entity_store(cls) -> EntityStore:
        from ..store.entity_store import EntityStore

        if (uid_storage := EntityStore.get_global_store()) is None:
            msg = f"Global EntityStore is not set. Please create an EntityStore instance and call set_as_global_store() on it before creating {cls.__name__} instances."
            raise ValueError(msg)
        return uid_storage

    @classmethod
    def by_uid_or_none[T: EntityRecordBase](cls: type[T], uid: Uid) -> T | None:
        if not isinstance(uid, Uid):
            msg = f"Expected 'uid' to be of type Uid, got {type(uid).__name__}."
            raise TypeError(msg)
        result = cls._get_entity_store().get_entity_record(uid)
        if result is None:
            return None
        if not isinstance(result, cls):
            msg = f"UID storage returned an instance of {type(result).__name__} instead of {cls.__name__}."
            raise TypeError(msg)
        return result

    @classmethod
    def by_uid[T: EntityRecordBase](cls: type[T], uid: Uid) -> T:
        if (result := cls.by_uid_or_none(uid)) is None:
            msg = f"Could not find an entity record of type {cls.__name__} for UID {uid}."
            raise ValueError(msg)
        return result

    @classmethod
    def narrow_to_uid[T: EntityRecordBase](cls: type[T], value: T | Uid) -> Uid:
        if isinstance(value, Uid):
            # try to convert to concrete entity record so we can test isinstance
            record = cls.by_uid_or_none(value)
            if record is None:
                # We cannot sanity check in this case - we want to support narrowing UIDs that may not yet exist in the store
                pass
            elif not isinstance(record, cls):
                msg = f"UID {value} does not correspond to an instance of class {cls.__name__}. Found instance of {type(record).__name__}."
                raise TypeError(msg)
            return value
        elif isinstance(value, cls):
            return value.uid
        else:
            msg = f"Value must be a {cls.__name__} or Uid, got {type(value)}"
            raise TypeError(msg)

    @classmethod
    def narrow_to_instance_or_none[T: EntityRecordBase](cls: type[T], value: T | Uid) -> T | None:
        if isinstance(value, cls):
            return value

        elif isinstance(value, Uid):
            record = cls.by_uid(value)
            if record is None:
                return None
            if not isinstance(record, cls):
                msg = f"UID {value} does not correspond to an instance of {cls.__name__}. Found instance of {type(record).__name__}."
                raise TypeError(msg)
            return record

        else:
            msg = f"Value must be a {cls.__name__} or Uid, got {type(value)}"
            raise TypeError(msg)

    @classmethod
    def narrow_to_instance[T: EntityRecordBase](cls: type[T], value: T | Uid) -> T:
        if (result := cls.narrow_to_instance_or_none(value)) is None:
            msg = f"Could not find an entity record of type {cls.__name__} for value {value}."
            raise ValueError(msg)
        return result

    # MARK: Entity
    @classmethod
    def register_entity_class(cls, entity_class: type[Entity]) -> None:
        from .entity import Entity

        if not issubclass(entity_class, Entity):
            msg = f"Expected 'entity_class' to be a subclass of EntityBase, got {entity_class.__name__}."
            raise TypeError(msg)
        if cls in ENTITY_CLASSES:
            msg = f"Entity record class {cls.__name__} is already registered with entity class {ENTITY_CLASSES[cls].__name__}."
            raise ValueError(msg)
        ENTITY_CLASSES[cls] = entity_class

    @classmethod
    def get_entity_class(cls) -> type[Entity]:
        if (entity_cls := ENTITY_CLASSES.get(cls)) is None:
            msg = f"Entity record class {cls.__name__} is not registered with any entity class. Please call 'register_entity_class' to register it."
            raise ValueError(msg)
        return entity_cls

    @property
    def entity_or_none(self) -> Entity | None:
        if self.reverted:
            return None

        from .entity import Entity

        return Entity.by_uid_or_none(self.uid)

    @property
    @override
    def entity(self) -> Entity:
        if (entity := self.entity_or_none) is None:
            msg = f"Entity record with UID {self.uid} is not associated with any Entity instance."
            raise ValueError(msg)
        return entity

    def call_entity_method(self, name: str, *args, **kwargs) -> Any:
        method = getattr(self.entity, name)
        return method(*args, **kwargs)

    # MARK: Parent
    PROPAGATE_INSTANCE_PARENT_FROM_PARENT_TO_CHILDREN: ClassVar[bool] = True

    @property
    @override
    def instance_parent(self) -> HierarchicalProtocol | NamedProtocol | None:
        return self.entity_or_none

    @property
    def record_parent_or_none(self) -> EntityRecordBase | None:
        if (entity := self.entity_or_none) is None:
            return None
        if (parent := entity.instance_parent) is None:
            return None

        from .entity_base import EntityBase

        record = parent.record_or_none if isinstance(parent, EntityBase) else parent
        if record is None or not isinstance(record, EntityRecordBase):
            return None
        return record.superseding_or_none

    @property
    def record_parent(self) -> EntityRecordBase:
        if (parent := self.record_parent_or_none) is None:
            msg = f"{type(self).__name__} instance {self.uid} has no valid entity record parent."
            raise ValueError(msg)
        return parent

    @property
    def entity_parent_or_none(self) -> Entity | None:
        if (entity := self.entity_or_none) is None:
            return None
        if (parent := entity.instance_parent) is None:
            return None
        from .entity import Entity

        entity = parent.entity_or_none if isinstance(parent, EntityRecordBase) else parent
        if entity is None or not isinstance(entity, Entity):
            return None
        return entity

    @property
    def entity_parent(self) -> Entity:
        if (parent := self.entity_parent_or_none) is None:
            msg = f"{type(self).__name__} instance {self.uid} has no valid entity parent."
            raise ValueError(msg)
        return parent

    # MARK: Version / Entity Log
    if TYPE_CHECKING:
        entity_log: EntityLog
    else:

        @property
        def entity_log(self) -> EntityLog:
            return self.entity.entity_log

    @field_validator("version", mode="before")
    @classmethod
    def _validate_version_before(cls, version: PositiveInt | None, info: ValidationInfo) -> PositiveInt:
        if version is None:
            version = typing_cast("PositiveInt", EntityLog(info.data["uid"]).next_version)
        return version

    @field_validator("version", mode="after")
    @classmethod
    def _validate_version(cls, version: PositiveInt, info: ValidationInfo) -> PositiveInt:
        entity_log = EntityLog(info.data["uid"])
        if version != entity_log.next_version:
            msg = f"Entity record version '{version}' does not match the next audit log version '{entity_log.version + 1}'. The version should be incremented when the entity is cloned as part of an update action."
            raise ValueError(msg)
        return version

    def is_newer_version_than(self, other: EntityRecordBase) -> bool:
        if not isinstance(other, EntityRecordBase):
            msg = f"Expected EntityRecordBase, got {type(other)}"
            raise TypeError(msg)
        if self.uid != other.uid:
            msg = f"Cannot compare versions of entities with different UIDs: {self.uid} vs {other.uid}"
            raise ValueError(msg)
        return self.version > other.version

    @property
    def superseded(self) -> bool:
        """Indicates whether this entity record instance has been superseded by another instance with an incremented version."""
        return self.reverted or self.entity_log.version > self.version

    @property
    def superseding_or_none[T: EntityRecordBase](self: T) -> T | None:
        if not self.superseded:
            return self
        return type(self).by_uid_or_none(self.uid)

    @property
    def superseding[T: EntityRecordBase](self: T) -> T:
        if (result := self.superseding_or_none) is None:
            msg = f"Entity record {self} has been superseded but the superseding entity record could not be found."
            raise ValueError(msg)
        return result

    def update[T: EntityRecordBase](self: T, **kwargs: Any) -> T:
        """Create a new instance of the entity record with the updated data.

        The new instance will have an incremented version and the same UID, superseding the current instance.
        """
        self.assert_update_allowed(allow_frozen_journal=True, force_session=False)

        # Validate data
        if not kwargs:
            msg = "No data provided to update the entity record."
            raise ValueError(msg)

        if "uid" in kwargs:
            msg = "Cannot update the 'uid' of an entity record. The UID is immutable and should not be changed."
            raise ValueError(msg)
        if "version" in kwargs:
            msg = "Cannot update the 'version' of an entity record. The version is managed by the entity record itself and should not be changed directly."
            raise ValueError(msg)

        args = {}
        for field_name in type(self).model_fields:
            target_name = self.reverse_field_alias(field_name)
            if field_name in kwargs:
                args[target_name] = kwargs[field_name]
            else:
                args[target_name] = self.__dict__[field_name]

        args.update(kwargs)
        args["uid"] = self.uid
        args["version"] = self.entity_log.next_version

        # Sanity check - name won't change
        if (new_name := self.entity.calculate_instance_name_from_dict(args)) != self.instance_name:
            msg = f"Updating the entity record cannot change its instance name. Original: '{self.instance_name}', New: '{new_name}'."
            raise ValueError(msg)

        # Update entity record
        new_record = type(self)(**args)

        # Sanity check
        if not isinstance(new_record, type(self)):
            msg = f"Expected new entity record to be an instance of {type(self).__name__}, got {type(new_record).__name__}."
            raise TypeError(msg)
        if new_record.instance_name != self.instance_name:
            msg = f"Updating the entity record cannot change its instance name. Original: '{self.instance_name}', New: '{new_record.instance_name}'."
            raise ValueError(msg)

        # Return updated entity record
        return new_record

    # MARK: Journal
    @staticmethod
    def _is_entity_record_attribute(name: str) -> bool:
        return hasattr(EntityRecordBase, name) or name in EntityRecordBase.model_fields or name in EntityRecordBase.model_computed_fields

    @classmethod
    def get_model_field_aliases(cls) -> frozendict[str, str]:
        aliases = getattr(cls, "model_field_aliases", None)
        if aliases is None:
            aliases = {}

            for name, info in cls.model_fields.items():
                if info.alias:
                    aliases[info.alias] = name

            aliases = frozendict(aliases)
            setattr(cls, "model_field_aliases", aliases)
        return aliases

    @classmethod
    def is_model_field_alias(cls, alias: str) -> bool:
        return cls.get_model_field_aliases().get(alias, None) is not None

    @classmethod
    def resolve_field_alias(cls, alias: str) -> str:
        return cls.get_model_field_aliases().get(alias, alias)

    @classmethod
    def get_model_field_reverse_aliases(cls) -> frozendict[str, str]:
        reverse = getattr(cls, "model_field_reverse_aliases", None)
        if reverse is None:
            reverse = {}

            for name, info in cls.model_fields.items():
                if info.alias:
                    reverse[name] = info.alias

            reverse = frozendict(reverse)
            setattr(cls, "model_field_reverse_aliases", reverse)
        return reverse

    @classmethod
    def reverse_field_alias(cls, name: str) -> str:
        return cls.get_model_field_reverse_aliases().get(name, name)

    @classmethod
    def is_model_field(cls, field: str) -> bool:
        return field in cls.model_fields

    @classmethod
    def is_computed_field(cls, field: str) -> bool:
        return field in cls.model_computed_fields

    _PROTECTED_FIELD_TYPES: ClassVar[tuple[type, ...]]

    @classmethod
    def _get_protected_field_types(cls) -> tuple[type, ...]:
        s = getattr(EntityRecordBase, "_PROTECTED_FIELD_TYPES", None)
        if s is not None:
            return s

        from ...collections import JournalledCollection, OrderedViewMutableSet

        default = (JournalledCollection, OrderedViewMutableSet, OrderedViewMutableSet, EntityLog, EntityDependents)
        setattr(EntityRecordBase, "_PROTECTED_FIELD_TYPES", default)
        return default

    @classmethod
    def _get_field_annotation(cls, field: str) -> Any | None:
        return type_hints.get_type_hint(cls, field)

    _PROTECTED_FIELD_LOOKUP: ClassVar[MutableMapping[str, bool]]

    @classmethod
    def is_protected_field_type(cls, field: str) -> bool:
        protected_field_lookup = getattr(cls, "_PROTECTED_FIELD_LOOKUP", None)
        if protected_field_lookup is None:
            protected_field_lookup = cls._PROTECTED_FIELD_LOOKUP = {}
        elif (result := protected_field_lookup.get(field)) is not None:
            return result

        annotation = cls._get_field_annotation(field)
        if annotation is None:
            msg = f"Field '{field}' not found in entity record type {cls.__name__} annotations."
            raise RuntimeError(msg)

        forbidden_types = cls._get_protected_field_types()
        result = False
        for hint in type_hints.iterate_type_hints(annotation, origin=True):
            origin = generics.get_origin(hint, passthrough=True)
            if issubclass(origin, forbidden_types):
                result = True
                break

        protected_field_lookup[field] = result
        return result

    # MARK: Children
    def is_reachable(self, *, recursive: bool = True, use_journal: bool = False) -> bool:
        return self.entity.is_reachable(recursive=recursive, use_journal=use_journal)

    @model_validator(mode="after")
    def _validate_valid_fields(self) -> Self:
        if __debug__:
            from .entity import Entity

            for uid in self.entity.iter_field_uids():
                entity = Entity.by_uid_or_none(uid)
                if entity is None:
                    msg = f"Entity record has a reference to non-existent entity UID {uid}."
                    raise ValueError(msg)
                if entity.deleted:
                    msg = f"Entity record has a reference to deleted entity UID {uid}."
                    raise ValueError(msg)
                if not entity.exists:
                    msg = f"Entity record has a reference to non-existent entity UID {uid}."
                    raise ValueError(msg)
                assert not entity.superseded, f"Entity record has a reference to superseded entity UID {uid}."

        return self

    # MARK: Annotations
    @field_validator("annotations", mode="before")
    @classmethod
    def _validate_annotations_before(cls, annotations: Any) -> frozenset:
        from ..annotation import Annotation

        if annotations is None:
            return frozenset()

        if not isinstance(annotations, AbstractSet):
            msg = f"Expected 'annotations' to be an AbstractSet, got {type(annotations).__name__}."
            raise TypeError(msg)

        for item in annotations:
            if not isinstance(item, Annotation):
                msg = f"Expected items in 'annotations' to be of type Annotation or Uid, got {type(item).__name__}."
                raise TypeError(msg)

        if not isinstance(annotations, frozenset):
            annotations = frozenset(annotations)

        return annotations

    # MARK: Dependents
    if TYPE_CHECKING:
        entity_dependents: EntityDependents
    else:

        @property
        def entity_dependents(self) -> EntityDependents:
            return self.entity.entity_dependents

    @property
    def dependent_uids(self) -> Iterable[Uid]:
        return self.entity_dependents.dependent_uids

    @property
    def dependents(self) -> Iterable[EntityRecordBase]:
        return self.entity_dependents.dependents

    # MARK: Dependencies
    @property
    def extra_dependencies(self) -> UidProxySet[EntityRecordBase]:
        from ...collections import UidProxySet

        return UidProxySet[EntityRecordBase](instance=self, field="extra_dependency_uids")

    # MARK: Dependency Events
    __entity_dependency_event_handler_records__: ClassVar[MutableSet[EntityDependencyEventHandlerBase]]

    @classmethod
    def __init_dependencies__(cls) -> None:
        cls.__entity_dependency_event_handler_records__ = set()

    @classmethod
    def register_dependency_event_handler(cls, record: EntityDependencyEventHandlerBase) -> None:
        cls.__entity_dependency_event_handler_records__.add(record)

    if script_info.is_unit_test():

        @classmethod
        def clear_dependency_event_handlers(cls) -> None:
            if hasattr(cls, "__entity_dependency_event_handler_records__"):
                cls.__entity_dependency_event_handler_records__.clear()
                cls.__init_dependencies__()

            for t in ENTITY_RECORD_SUBCLASSES:
                if issubclass(t, cls):
                    if hasattr(t, "__entity_dependency_event_handler_records__"):
                        t.__entity_dependency_event_handler_records__.clear()
                        t.__init_dependencies__()

    @classmethod
    def iter_dependency_event_handlers(cls) -> Iterable[EntityDependencyEventHandlerBase]:
        for subclass in cls.__mro__:
            if not issubclass(subclass, EntityRecordBase):
                continue
            if not hasattr(subclass, "__entity_dependency_event_handler_records__"):
                continue
            yield from subclass.__entity_dependency_event_handler_records__

    def _call_dependency_event_handlers(self, event: EntityDependencyEventType, record: EntityRecordBase, journal: Journal) -> bool:
        from .entity_record import EntityRecord

        assert isinstance(self, EntityRecord), f"Expected EntityRecord, got {type(self).__name__} instead."
        assert isinstance(record, EntityRecord), f"Expected EntityRecord, got {type(record).__name__} instead."

        matched = False
        for ev_record in type(self).iter_dependency_event_handlers():
            matched_current = ev_record(owner=self, event=event, record=record, journal=journal)
            matched |= matched_current

            # Abort if one of the handlers marks this entity for deletion
            if matched_current and self.marked_for_deletion:
                break

        return matched

    def on_dependency_updated(self, source: Journal) -> None:
        if self.marked_for_deletion:
            msg = f"Entity record {self} is already marked for deletion or deleted, cannot process dependency deletion."
            raise RuntimeError(msg)

        parent = self.record_parent_or_none
        record = source.record

        self.log.debug(t"Entity record {self} received invalidation from dependency entity record {record}.")

        # If the source record is the parent of this entity record, then we should confirm we are still reachable
        if record is parent:
            if not self.is_reachable(use_journal=True, recursive=False):
                self.log.warning(t"Entity record {self} is no longer reachable from its parent {parent}, deleting itself.")
                self.delete()
                return

        # Propagate the update to any fields that reference the source entity record
        if record is not parent:
            self._propagate_dependency_update(source)

        # Call event handlers
        self._call_dependency_event_handlers(event=EntityDependencyEventType.UPDATED, record=record, journal=source)

    def _propagate_dependency_update(self, source: Journal) -> None:
        from ...collections import HasJournalledTypeCollectionProtocol, OnItemUpdatedCollectionProtocol

        record = source.record
        entity = record.entity

        # Loop through entity record fields, and search for OrderedViewMutableSets that referenced the source entity record
        for nm in type(self).model_fields:
            original = getattr(self, nm, None)
            if original is None:
                continue

            elif original is entity:
                # Direct reference to the entity / entity record
                value = self.journal.get_field(nm, wrap=True)
                if value is not record:
                    continue

                self.log.debug(t"Propagating dependency {record} update to field '{nm}'")
                self.journal.set_field(nm, entity)

            elif isinstance(original, HasJournalledTypeCollectionProtocol):
                self.log.debug(t"Checking collection field '{nm}' for dependency {record}")
                edited = self.is_journal_field_edited(nm)
                value = self.journal.get_field(nm, wrap=False) if edited else original

                # Only propagate if the invalidated child is present in both the wrapped set *and* the original set
                # (this avoids propagating invalidations for items that have been added or removed from the set in the same session as the invalidation)
                if entity not in original or (value is not original and entity not in value):
                    continue

                if not edited:
                    value = self.journal.get_field(nm, wrap=True)
                assert isinstance(value, OnItemUpdatedCollectionProtocol), f"Expected OnItemUpdatedCollectionProtocol, got {type(value)}"
                assert entity in value, f"Expected collection to contain {entity}, but it does not."

                self.log.debug(t"Propagating dependency {record} update to collection '{nm}'")
                value.on_item_updated(record, source)

    def on_dependency_deleted(self, source: Journal) -> None:
        if self.marked_for_deletion:
            msg = f"Entity record {self} is already marked for deletion or deleted, cannot process dependency deletion."
            raise RuntimeError(msg)

        record = source.record

        self.log.debug(t"Entity record {self} received deletion notice from dependency entity record {record}.")

        # If the source record is the parent of this entity record, then we should delete ourselves too
        if (parent := self.record_parent_or_none) is not None and record.uid == parent.uid:
            if parent.uid == record.uid:
                self.log.warning(t"Entity record {self} is a child of deleted entity record {record}, deleting itself too.")
                self.delete()
                return

        # Sanity check: source record cannot be a child of this entity record
        if record.uid in self.journal_children_uids:
            msg = f"Entity record {record} is a child of {self} and therefore the latter cannot be deleted."
            raise RuntimeError(msg)

        # Call event handlers
        self._call_dependency_event_handlers(event=EntityDependencyEventType.DELETED, record=record, journal=source)
        if self.marked_for_deletion:
            return

        # If the source record is in our extra dependencies, we remove it
        if record.uid in self.extra_dependency_uids:
            self.journal.remove_dependency(record.uid)

    # MARK: Serialization
    @field_serializer("annotations", mode="plain")
    @classmethod
    def _serialize_annotations(cls, annotations: frozenset) -> tuple[Any, ...]:
        return tuple(annotations)

    # MARK: Utilities
    def sort_key(self) -> SupportsRichComparison:
        return self.uid

    @override
    def __hash__(self) -> int:
        return hash((self.uid, self.version))

    @override
    def __eq__(self, other: object) -> bool:
        if isinstance(other, EntityRecordBase):
            return self.uid == other.uid and self.version == other.version
        else:
            return False

    @override
    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def _customize_str_repr(self, spr: str) -> str:
        assert spr and spr[0] == "<", f"Expected string representation to start with '<', got {spr} instead."  # noqa: PT018

        result = spr.removesuffix(">")
        result += f" v{self.version}"
        if self.deleted:
            result += " (X)"
        elif self.superseded:
            result += " (S)"

        result = result.replace(f"{type(self).__name__.removesuffix('Record')}@", "")
        return result + ">"

    @override
    def __str__(self) -> str:
        return self._customize_str_repr(super(HierarchicalMixinMinimal, self).__str__())

    @override
    def __repr__(self) -> str:
        return self._customize_str_repr(super(HierarchicalMixinMinimal, self).__repr__())
