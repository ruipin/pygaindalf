# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import annotationlib

from pydantic import ConfigDict, Field, PrivateAttr, field_validator, InstanceOf
from typing import Any, TYPE_CHECKING, ClassVar, override, get_origin, get_args, Literal, Final, Union, Iterator, Callable, cast as typing_cast
from frozendict import frozendict
import builtins

from collections.abc import Sequence, Mapping, Set, MutableSet

if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison
    from .session import Session

from ...util.models import LoggableHierarchicalModel
from ...util.callguard import CallguardClassOptions

from ..models.uid import Uid

from ..models.entity.entity import Entity
from ..models.entity.superseded import superseded_check

from ..collections.journalled import JournalledCollection, JournalledMapping, JournalledSequence, JournalledSet, JournalledOrderedViewSet
from ..collections.ordered_view import OrderedViewSet, OrderedViewFrozenSet


class EntityJournal(LoggableHierarchicalModel):
    __callguard_class_options__ = CallguardClassOptions['EntityJournal'](
        decorator=superseded_check,
        decorate_public_methods=True,
        allow_same_module=True,
        decorate_ignore_patterns=('invalid','superseded','dirty','entity_uid','mark_invalid','commit_yield_hierarchy','get_diff')
    )

    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        validate_assignment=True,
    )

    PROPAGATE_TO_CHILDREN : ClassVar[bool] = False


    # MARK: Subclassing
    # We rely on init=False on subclasses to convince the type checker that fields do not get exposed in the constructor
    # as such we must swallow that parameter here
    def __init_subclass__(cls, *, init : bool = False):
        pass


    # MARK: Entity
    entity : InstanceOf[Entity] = Field(description="The entity associated with this journal entry.")

    @property
    def entity_uid(self) -> Uid:
        return self.entity.uid

    @property
    def version(self) -> int:
        return self.entity.version

    @property
    def session(self) -> Session:
        return self.entity.session

    @override
    def __hash__(self) -> int:
        return hash((self.__class__.__name__, hash(self.entity)))

    @field_validator('entity', mode='before')
    def _validate_entity(entity : Any) -> Entity:
        if not isinstance(entity, Entity):
            raise TypeError(f"Expected Entity, got {type(entity).__name__}")

        if entity.superseded:
            raise ValueError(f"EntityJournal.entity '{entity}' is superseded.")

        return entity

    @override
    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.entity!s})"

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}:{self.entity!r}>"

    @property
    def instance_name(self) -> str:
        return f"{self.__class__.__name__}({self.entity.uid})"

    def sort_key(self) -> SupportsRichComparison:
        # Delegate to entity sort key, but we pretend to be the entity for this call
        return type(self.entity).sort_key(typing_cast(Entity, self))


    # MARK: Superseded
    _invalid : bool = PrivateAttr(default=False)
    @property
    def invalid(self) -> bool:
        try:
            return getattr(self, '_invalid', False)
        except:
            return False

    def mark_invalid(self) -> None:
        self._invalid = True

    @property
    def superseded(self) -> bool:
        return self.invalid or self.entity.superseded

    @property
    def dirty(self) -> bool:
        if self._dirty_children:
            return True
        for attr, value in self._updates.items():
            if isinstance(value, (JournalledSequence, JournalledMapping, JournalledSet)):
                if value.edited:
                    return True
            else:
                return True
        return False


    # MARK: Fields API
    _updates : dict[str, Any] = PrivateAttr(default_factory=dict)

    @staticmethod
    def _is_journal_attribute(name: str) -> bool:
        return hasattr(EntityJournal, name) or name in EntityJournal.model_fields or name in EntityJournal.model_computed_fields

    def is_computed_field(self, field : str) -> bool:
        return self.entity.is_computed_field(field)

    def is_field_alias(self, field : str) -> bool:
        return self.entity.is_model_field_alias(field)

    def is_model_field(self, field : str) -> bool:
        return self.entity.is_model_field(field)

    def has_field(self, field : str) -> bool:
        return self.is_model_field(field) or self.is_computed_field(field)

    def can_modify(self, field : str) -> bool:
        info = self.entity.__class__.model_fields.get(field, None)
        if info is None:
            return False

        if not isinstance((extra := info.json_schema_extra), dict):
            return True

        return not extra.get('readOnly', False)

    def is_protected_field_type(self, field : str) -> bool:
        FORBIDDEN_TYPES = (JournalledCollection, OrderedViewSet, OrderedViewFrozenSet)

        annotations = annotationlib.get_annotations(self.entity.__class__, format=annotationlib.Format.VALUE)
        annotation = annotations.get(field, None)
        if annotation is None:
            raise RuntimeError(f"Field '{field}' not found in entity type {self.entity.__class__.__name__} annotations.")

        if isinstance(annotation, Union):
            for arg in get_args(annotation):
                if issubclass(arg, FORBIDDEN_TYPES):
                    return True
            return False
        else:
            origin = get_origin(annotation) or annotation
            return issubclass(origin, FORBIDDEN_TYPES)

    def is_field_updated(self, field : str) -> bool:
        return field in self._updates

    def get_original_field(self, field : str) -> Any:
        if not self.has_field(field):
            raise AttributeError(f"Entity of type {self.entity.__class__.__name__} does not have field '{field}'.")
        return super(Entity, self.entity).__getattribute__(field)

    def _wrap_field(self, field : str, original : Any) -> Any:
        new = original

        if isinstance(original, OrderedViewFrozenSet):
            journalled_type = original.get_journalled_type()
            new = journalled_type(original, instance_parent=self, instance_name=field)
        elif isinstance(original, Sequence) and not isinstance(original, (str, bytes)):
            new = JournalledSequence(original, instance_parent=self, instance_name=field)
        elif isinstance(original, Mapping):
            new = JournalledMapping(original, instance_parent=self, instance_name=field)
        elif isinstance(original, Set):
            new = JournalledSet(original, instance_parent=self, instance_name=field)
        else:
            return original

        self._updates[field] = new
        self.propagate()

        return new

    def set_field[T](self, field : str, value : T) -> T:
        field = self.entity.resolve_field_alias(field)

        has_update = field in self._updates
        if not has_update and not self.has_field(field):
            raise AttributeError(f"Entity of type {self.entity.__class__.__name__} does not have field '{field}'.")

        if not self.can_modify(field):
            raise AttributeError(f"Field '{field}' of entity type {self.entity.__class__.__name__} is read-only.")

        original = self.get_original_field(field)
        if value is original:
            if has_update:
                del self._updates[field]
        else:
            if self.is_protected_field_type(field):
                raise AttributeError(f"Field '{field}' of entity type {self.entity.__class__.__name__} is protected and cannot be modified. Use the collection's methods to modify it instead.")
            self._updates[field] = value

        self.propagate()

        return value

    def get_field(self, field : str, *, wrap : bool = True) -> Any:
        field = self.entity.resolve_field_alias(field)

        if field in self._updates:
            return self._updates[field]

        original = self.get_original_field(field)
        return self._wrap_field(field, original) if wrap else original

    if not TYPE_CHECKING:
        @override
        def __getattribute__(self, name: str) -> Any:
            # Short-circuit cases
            if (
                # Short-circuit private and 'Entity' attributes
                (name.startswith('_') or EntityJournal._is_journal_attribute(name)) or
                # If this is not a model field
                (not self.is_model_field(name)) or
                # If not in a session, return the normal attribute
                (self.superseded)
            ):
                return super().__getattribute__(name)

            # Otherwise, use the journal to get the attribute
            return self.get_field(name)

    @override
    def __setattr__(self, name: str, value: Any) -> None:
        if (
            # Short-circuit private and 'Entity' attributes
            (name.startswith('_') or EntityJournal._is_journal_attribute(name)) or
            # If this is not a model field
            (not self.is_model_field(name)) or
            # If not in a session, set the normal attribute
            (self.superseded)
        ):
            return super().__setattr__(name, value)

        # Otherwise set attribute on the journal
        return self.set_field(name, value)


    def get_diff(self) -> frozendict[str, Any]:
        if (cached := getattr(self, '_diff', None)) is not None:
            return cached

        diff = self._updates.copy()
        for k, v in self._updates.items():
            if isinstance(v, JournalledCollection):
                if not v.edited:
                    del diff[k]
                else:
                    diff[k] = tuple(v.journal)

        result = frozendict(diff)
        if self.invalidated:
            self._diff = result

        return result


    # MARK: Propagation
    _dirty_children : MutableSet[Uid] = PrivateAttr(default_factory=set)
    _propagated_has_updates : bool = PrivateAttr(default=False)

    def _update_child_dirty_state(self, child : EntityJournal, dirty : bool | None = None):
        if dirty is None:
            dirty = child.dirty

        if dirty:
            self._dirty_children.add(child.entity_uid)
        else:
            self._dirty_children.discard(child.entity_uid)

        self.propagate()

    def propagate(self) -> None:
        """
        Propagate whether we are dirty to the parent entity's journal
        """

        # Check if the dirty state has changed since the last time we propagated to our parent journal
        has_updates = bool(self._updates)
        if has_updates == self._propagated_has_updates:
            return

        # Propagate to parent journal
        parent = self.entity.instance_parent
        if parent is None:
            return
        if not isinstance(parent, Entity):
            if parent is self.entity.session_manager.instance_parent:
                return
            raise TypeError("EntityJournal can only propagate when the parent is an Entity or the SessionManager parent.")

        parent_journal = parent.journal
        parent_journal._update_child_dirty_state(self, has_updates)

        # Cache the last propagated dirty state
        self._propagated_has_updates = has_updates



    # MARK: Invalidation
    def on_dependency_invalidated(self, source: EntityJournal) -> None:
        # Loop through entity fields, and search for OrderedViewSets that referenced the source entity
        for nm, info in self.entity.__class__.model_fields.items():
            original = self.get_original_field(nm)
            uid = source.entity_uid

            if isinstance(original, OrderedViewFrozenSet):
                value = self.get_field(nm, wrap=False)

                # Only propagate if the invalidated child is present in both the wrapped set *and* the original set
                # (this avoids propagating invalidations for items that have been added or removed from the set in the same session as the invalidation)
                if uid not in original or (value is not original and uid not in value):
                    continue

                if not self.is_field_updated(nm):
                    value = self._wrap_field(nm, value)
                assert isinstance(value, JournalledOrderedViewSet)

                value.on_item_journal_invalidated(source)


    # MARK: Commit
    _invalidated : bool = PrivateAttr(default=False)

    @property
    def invalidated(self) -> bool:
        return self._invalidated

    def invalidate(self) -> None:
        if self._invalidated:
            raise RuntimeError(f"Journal {self} is already invalidated.")
        self._invalidated = True

        for dep in self.entity.dependent_uids:
            entity = Entity.by_uid(dep)

            if not entity.marked_for_deletion:
                entity.on_dependency_invalidated(self)

    def commit_yield_hierarchy(self, condition : Callable[[EntityJournal], bool]) -> Iterator[EntityJournal]:
        """
        Return a flat ordered set of all journals in this hierarchy
        """
        if not condition(self):
            return

        # Iterate dirty children journals
        for child_uid in self._dirty_children:
            child = Entity.by_uid_or_none(child_uid)
            if child is None or (child_journal := child.get_journal(create=False)) is None:
                continue

            if not condition(child_journal):
                continue

            for inv in child_journal.commit_yield_hierarchy(condition):
                yield inv

        if not condition(self):
            raise RuntimeError(f"Journal {self} was invalidated or commited during child invalidation.")

        # Yield self, then return
        yield self

    def commit(self) -> Entity:
        if not self.dirty:
            return self.entity

        self.log.debug("Committing journal for entity %s", self.entity)

        # Collect all updates
        updates = {}

        for attr, update in self._updates.items():
            if isinstance(update, (JournalledSequence, JournalledMapping, JournalledSet)):
                if not update.edited:
                    continue

            updates[attr] = update

        if not updates:
            return self.entity

        self.log.debug("Updates to apply to entity %s: %s", self.entity, repr(updates))

        # Update the entity
        new_entity = self._new_entity = self.entity.update(
            **updates
        )

        self.log.debug("New entity created: %s (v%d)", new_entity, new_entity.version)

        # Done
        return new_entity