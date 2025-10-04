# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Iterable, Mapping, MutableSet, Sequence
from collections.abc import Set as AbstractSet
from functools import cached_property
from typing import TYPE_CHECKING, Any, ClassVar, override
from typing import cast as typing_cast

from frozendict import frozendict
from pydantic import ConfigDict, Field, InstanceOf, PrivateAttr, field_validator

from ...util.callguard import CallguardClassOptions
from ...util.models import LoggableHierarchicalModel
from ..collections.journalled import JournalledCollection, JournalledMapping, JournalledSequence, JournalledSet
from ..collections.ordered_view import OrderedViewSet
from ..models.entity import Entity, EntityImpl, EntityRecord
from ..util.superseded import SupersededError, superseded_check
from ..util.uid import Uid


if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison

    from ..collections import UidProxyMutableSet
    from ..models.annotation import Annotation
    from .session import Session


class Journal(LoggableHierarchicalModel, EntityImpl[MutableSet[Uid]]):
    __callguard_class_options__ = CallguardClassOptions["Journal"](
        decorator=superseded_check,
        decorate_public_methods=True,
        decorate_ignore_patterns=(
            "superseded",
            "_marked_superseded",
            "dirty",
            "deleted",
            "marked_for_deletion",
            "uid",
            "mark_superseded",
            "freeze",
            "commit_yield_hierarchy",
            "get_diff",
            "instance_name",
            "instance_hierarchy",
        ),
    )

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )

    PROPAGATE_TO_CHILDREN: ClassVar[bool] = False

    # MARK: Subclassing
    # We rely on init=False on subclasses to convince the type checker that fields do not get exposed in the constructor
    # as such we must swallow that parameter here
    def __init_subclass__(cls, *, init: bool = False, unsafe_hash: bool = False) -> None:
        super().__init_subclass__()

    # MARK: EntityRecord
    record: InstanceOf[EntityRecord] = Field(description="The entity record associated with this journal entry.")

    @property
    @override
    def uid(self) -> Uid:  # pyright: ignore[reportIncompatibleVariableOverride]
        return self.record.uid

    if not TYPE_CHECKING:

        @property
        def version(self) -> int:
            return self.record.version

    @override
    def __hash__(self) -> int:
        return hash((type(self).__name__, hash(self.record)))

    @field_validator("record", mode="before")
    @classmethod
    def _validate_record(cls, record: Any) -> EntityRecord:
        if not isinstance(record, EntityRecord):
            msg = f"Expected EntityRecordBase, got {type(record).__name__}"
            raise TypeError(msg)

        if record.superseded:
            msg = f"EntityJournal.record '{record}' is superseded."
            raise SupersededError(msg)

        return record

    @property
    def entity_or_none(self) -> Entity | None:
        return self.record.entity_or_none

    @property
    def entity(self) -> Entity:
        return self.record.entity

    @override
    def __str__(self) -> str:
        return f"{type(self).__name__}({self.record!s})"

    @override
    def __repr__(self) -> str:
        return f"<{type(self).__name__}:{self.record!r}>"

    @property
    @override
    def instance_name(self) -> str:
        return f"{type(self).__name__}({self.record.uid})"

    def sort_key(self) -> SupportsRichComparison:
        # Delegate to entity sort key, but we pretend to be the entity for this call
        return type(self.record).sort_key(typing_cast("EntityRecord", self))

    # MARK: Superseded
    _marked_superseded: bool = PrivateAttr(default=False)

    def mark_superseded(self) -> None:
        self.freeze()
        self._marked_superseded = True

    @property
    def superseded(self) -> bool:
        try:
            if getattr(self, "_marked_superseded", False):
                return True
        except (TypeError, AttributeError, KeyError):
            pass

        return self.deleted or self.record.superseded

    @property
    def dirty(self) -> bool:
        if self._dirty_children:
            return True
        if self._marked_for_deletion:
            return True
        for value in self._updates.values():
            if isinstance(value, JournalledCollection):
                if value.edited:
                    return True
            else:
                return True
        return False

    def _on_dirtied(self) -> None:
        self._reset_children_uids_cache()
        self._propagate_dirty()
        self._reset_notified_dependents()

    # MARK: Session
    @property
    def session(self) -> Session:
        parent = self.instance_parent
        if parent is None:
            msg = f"EntityJournal {self} has no parent Session."
            raise RuntimeError(msg)
        from .session import Session

        if not isinstance(parent, Session):
            msg = f"EntityJournal {self} parent is not a Session."
            raise TypeError(msg)
        return parent

    # MARK: Frozen
    _frozen: bool = PrivateAttr(default=False)

    @property
    def frozen(self) -> bool:
        return self._frozen

    def freeze(self) -> None:
        self._frozen = True

        for v in self._updates.values():
            if isinstance(v, JournalledCollection):
                v.freeze()

    # MARK: Fields API
    _updates: dict[str, Any] = PrivateAttr(default_factory=dict)

    @staticmethod
    def _is_journal_attribute(name: str) -> bool:
        return hasattr(Journal, name) or name in Journal.model_fields or name in Journal.model_computed_fields

    def is_computed_field(self, field: str) -> bool:
        return self.record.is_computed_field(field)

    def is_field_alias(self, field: str) -> bool:
        return self.record.is_model_field_alias(field)

    def is_model_field(self, field: str) -> bool:
        return self.record.is_model_field(field)

    def has_field(self, field: str) -> bool:
        return self.is_model_field(field) or self.is_computed_field(field)

    def can_modify(self, field: str) -> bool:
        info = type(self.record).model_fields.get(field, None)
        if info is None:
            return False

        if not isinstance((extra := info.json_schema_extra), dict):
            return True

        return not extra.get("readOnly", False)

    def is_field_edited(self, field: str) -> bool:
        value = self._updates.get(field, None)
        if value is None:
            return False
        return value.edited if isinstance(value, JournalledCollection) else True

    def get_original_field(self, field: str) -> Any:
        if not self.has_field(field):
            msg = f"EntityRecord of type {type(self.record).__name__} does not have field '{field}'."
            raise AttributeError(msg)
        return super(EntityRecord, self.record).__getattribute__(field)

    def _wrap_field(self, field: str, original: Any) -> Any:
        if field in self._updates:
            msg = f"Field '{field}' of journal {self} is already wrapped."
            raise RuntimeError(msg)

        new = original

        if isinstance(original, OrderedViewSet):
            journalled_type = original.get_journalled_type()
            new = journalled_type(original, instance_parent=self, instance_name=field)
        elif isinstance(original, Sequence) and not isinstance(original, (str, bytes)):
            new = JournalledSequence(original, instance_parent=self, instance_name=field)
        elif isinstance(original, Mapping):
            new = JournalledMapping(original, instance_parent=self, instance_name=field)
        elif isinstance(original, AbstractSet):
            new = JournalledSet(original, instance_parent=self, instance_name=field)
        else:
            return original

        if self._frozen:
            msg = f"Cannot wrap field '{field}' of frozen journal {self}."
            raise RuntimeError(msg)

        self._updates[field] = new
        self._on_dirtied()

        return new

    def set_field[T](self, field: str, value: T) -> T:
        field = self.record.resolve_field_alias(field)

        has_update = field in self._updates
        if not has_update and not self.has_field(field):
            msg = f"EntityRecord of type {type(self.record).__name__} does not have field '{field}'."
            raise AttributeError(msg)

        if not self.can_modify(field):
            msg = f"Field '{field}' of entity type {type(self.record).__name__} is read-only."
            raise AttributeError(msg)

        current = self.get_field(field, wrap=False)
        if value is current:
            return value

        if self._frozen:
            msg = f"Cannot modify field '{field}' of frozen journal {self}."
            raise RuntimeError(msg)

        original = self.get_original_field(field)

        if value is original:
            if has_update:
                del self._updates[field]
        else:
            if self.record.is_protected_field_type(field):
                msg = f"Field '{field}' of record type {type(self.record).__name__} is protected and cannot be modified. Use the collection's methods to modify it instead."
                raise AttributeError(msg)
            self._updates[field] = value

        self._on_dirtied()

        return value

    def get_field(self, field: str, *, wrap: bool = True) -> Any:
        if self.superseded:
            msg = "Cannot get field from a superseded journal."
            raise SupersededError(msg)

        field = self.record.resolve_field_alias(field)

        if field in self._updates:
            return self._updates[field]

        original = self.get_original_field(field)
        return self._wrap_field(field, original) if wrap else original

    if not TYPE_CHECKING:

        @override
        def __getattribute__(self, name: str) -> Any:
            # Short-circuit cases
            if (
                # Short-circuit private and 'EntityRecord' attributes
                (name.startswith("_") or Journal._is_journal_attribute(name))
                or
                # If this is not a model field
                (not self.is_model_field(name))
                or
                # If not in a session, return the normal attribute
                (self.superseded)
            ):
                return super().__getattribute__(name)

            # Otherwise, use the journal to get the attribute
            return self.get_field(name)

    @override
    def __setattr__(self, name: str, value: Any) -> None:
        if (
            # Short-circuit private and 'EntityRecord' attributes
            (name.startswith("_") or Journal._is_journal_attribute(name))
            or
            # If this is not a model field
            (not self.is_model_field(name))
            or
            # If not in a session, set the normal attribute
            (self.superseded)
        ):
            return super().__setattr__(name, value)

        # Otherwise set attribute on the journal
        return self.set_field(name, value)

    def on_journalled_collection_edit(self, collection: JournalledCollection) -> None:
        if self._frozen:
            msg = f"Cannot modify field '{collection.instance_name}' of frozen journal {self}."
            raise RuntimeError(msg)

        self._on_dirtied()

    def get_diff(self) -> frozendict[str, Any]:
        if (cached := getattr(self, "_diff", None)) is not None:
            return cached

        diff = self._updates.copy()
        for k, v in self._updates.items():
            if isinstance(v, JournalledCollection):
                if not v.edited:
                    del diff[k]
                else:
                    diff[k] = tuple(v.journal)

        result = frozendict(diff)
        if self._frozen:
            self._diff = result

        return result

    # MARK: Dirty Propagation
    _dirty_children: MutableSet[Uid] = PrivateAttr(default_factory=set)
    _propagated_dirty: bool = PrivateAttr(default=False)

    def _update_child_dirty_state(self, child: Journal, *, dirty: bool | None = None) -> None:
        if dirty is None:
            dirty = child.dirty

        if dirty:
            self._dirty_children.add(child.uid)
        else:
            self._dirty_children.discard(child.uid)

        self._propagate_dirty()

    def _propagate_dirty(self) -> None:
        """Propagate whether we are dirty to the parent entity's journal."""
        # Check if the dirty state has changed since the last time we propagated to our parent journal
        dirty = self.dirty
        if dirty == self._propagated_dirty:
            return

        # Propagate to parent journal
        if (parent := self.record.record_parent_or_none) is None:
            return

        parent_journal = parent.journal
        parent_journal._update_child_dirty_state(self, dirty=dirty)  # noqa: SLF001

        # Cache the last propagated dirty state
        self._propagated_dirty = dirty

    # MARK: Deletion
    _marked_for_deletion: bool = PrivateAttr(default=False)

    @property
    def marked_for_deletion(self) -> bool:
        return self._marked_for_deletion

    _deleted: bool = PrivateAttr(default=False)

    @property
    def deleted(self) -> bool:
        try:
            return getattr(self, "_deleted", False)
        except (TypeError, AttributeError, KeyError):
            return False

    def delete(self) -> None:
        if self._marked_for_deletion:
            return

        self._marked_for_deletion = True

        # Once marked for deletion, this journal will no longer be used to make updates to the entity
        self._updates.clear()
        self.freeze()

        # Delete all children recursively
        self._propagate_dirty()
        self.record.propagate_deletion()

    # MARK: Dependent Notifications
    _notified_dependents: bool = PrivateAttr(default=False)

    @property
    def notified_dependents(self) -> bool:
        return self._notified_dependents

    def notify_dependents(self) -> None:
        if self._notified_dependents:
            msg = f"Journal {self} has already notified its dependents of changes."
            raise RuntimeError(msg)

        self._notified_dependents = True

        if not self.dirty:
            return

        deletion = self._marked_for_deletion
        self.log.debug(t"Notifying dependents of pending {'deletion' if deletion else 'update'}...")

        for dep in self.record.dependent_uids:
            record = EntityRecord.by_uid(dep)

            if not record.marked_for_deletion:
                if deletion:
                    record.on_dependency_deleted(self)
                else:
                    record.on_dependency_updated(self)

    def _reset_notified_dependents(self) -> None:
        if not self._notified_dependents:
            return

        self._notified_dependents = False
        self.session.on_journal_reset_notified_dependents(self)

    # MARK: Commit
    _committed: bool = PrivateAttr(default=False)

    @property
    def committed(self) -> bool:
        return self._committed

    def commit(self) -> EntityRecord | None:
        assert self._notified_dependents, f"Cannot commit journal {self} before notifying dependents."
        assert not self._committed, f"Journal {self} has already been committed."
        self.freeze()

        if not self.dirty:
            self.mark_superseded()
            return self.record

        deletion = self._marked_for_deletion
        self.log.debug(t"Committing entity {'deletion' if deletion else 'update'}...")

        if self._marked_for_deletion:
            self._commit_delete()
            result = None
        else:
            result = self._commit_update()

        self._committed = True
        self.mark_superseded()
        return result

    def _commit_update(self) -> EntityRecord:
        self.log.debug("Committing update")

        # Collect all updates
        updates = {}

        for attr, update in self._updates.items():
            if isinstance(update, (JournalledSequence, JournalledMapping, JournalledSet)):
                if not update.edited:
                    continue

            updates[attr] = update

        if not updates:
            return self.record

        self.log.debug("Updates to apply: %s", updates)

        # Update the entity
        new_record = self._new_entity = self.record.update(**updates)

        self.log.debug("New entity record created: %s version %d", new_record, new_record.version)

        # Done
        return new_record

    def _commit_delete(self) -> None:
        assert self._marked_for_deletion, f"Cannot commit deletion of journal {self} that is not marked for deletion."
        assert not self._deleted, f"Journal {self} has already been deleted."

        self.log.debug("Committing deletion")

        self.record.apply_deletion()
        self._deleted = True

    # MARK: Children
    def iter_children_uids(self) -> Iterable[Uid]:
        yield from self.record.iter_children_uids(use_journal=True)

    @cached_property
    def children_uids(self) -> Iterable[Uid]:
        return frozenset(self.iter_children_uids())

    def _reset_children_uids_cache(self) -> None:
        self.__dict__.pop("children_uids", None)

    # MARK: Annotations
    @property
    def annotations(self) -> UidProxyMutableSet[Annotation]:
        from ..collections import UidProxyMutableSet
        from ..models.annotation import Annotation

        klass = UidProxyMutableSet[Annotation]
        return klass(instance=self, field="annotation_uids", source=klass)

    # MARK: Dependencies
    @property
    def extra_dependencies(self) -> UidProxyMutableSet[Entity]:
        from ..collections import UidProxyMutableSet

        klass = UidProxyMutableSet[Entity]
        return klass(instance=self, field="extra_dependency_uids", source=klass)

    def add_dependency(self, record_or_uid: EntityRecord | Uid) -> None:
        uid = EntityRecord.narrow_to_uid(record_or_uid)
        if uid in self.extra_dependency_uids:
            return
        self.extra_dependency_uids.add(uid)

    def remove_dependency(self, record_or_uid: EntityRecord | Uid) -> None:
        uid = EntityRecord.narrow_to_uid(record_or_uid)
        if uid not in self.extra_dependency_uids:
            return
        self.extra_dependency_uids.discard(uid)
