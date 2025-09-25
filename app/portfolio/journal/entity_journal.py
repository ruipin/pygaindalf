# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import annotationlib

from pydantic import ConfigDict, Field, PrivateAttr, field_validator, InstanceOf
from typing import Any, TYPE_CHECKING, ClassVar, override, get_origin, get_args, Iterable, Literal, Final, Union, Iterator, Callable, cast as typing_cast
from frozendict import frozendict
from functools import cached_property
from collections.abc import Sequence, Mapping, Set, MutableSet

from ...util.models import LoggableHierarchicalModel
from ...util.callguard import CallguardClassOptions

from ..models.uid import Uid

from ..models.entity import Entity, EntityBase
from ..models.entity.superseded import superseded_check

from ..collections.journalled import JournalledCollection, JournalledMapping, JournalledSequence, JournalledSet, JournalledOrderedViewSet
from ..collections.ordered_view import OrderedViewSet, OrderedViewFrozenSet


if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison
    from ..collections.uid_proxy import UidProxySet
    from .session import Session
    from ..models.annotation import Annotation


class EntityJournal(LoggableHierarchicalModel, EntityBase[MutableSet[Uid]]):
    __callguard_class_options__ = CallguardClassOptions['EntityJournal'](
        decorator=superseded_check,
        decorate_public_methods=True,
        decorate_ignore_patterns=('superseded','dirty','entity_uid','mark_superseded','freeze','commit_yield_hierarchy','get_diff','instance_name','instance_hierarchy')
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
    _marked_superseded : bool = PrivateAttr(default=False)
    def mark_superseded(self) -> None:
        self.freeze()
        self._marked_superseded = True

    @property
    def superseded(self) -> bool:
        try:
            marked_superseded = self._marked_superseded
        except:
            marked_superseded = False
        return marked_superseded or self.entity.superseded or self.entity.marked_for_deletion

    @property
    def dirty(self) -> bool:
        if self._dirty_children:
            return True
        for attr, value in self._updates.items():
            if isinstance(value, JournalledCollection):
                if value.edited:
                    return True
            else:
                return True
        return False


    # MARK: Frozen
    _frozen : bool = PrivateAttr(default=False)

    @property
    def frozen(self) -> bool:
        return self._frozen

    def freeze(self) -> None:
        self._frozen = True

        for k, v in self._updates.items():
            if isinstance(v, JournalledCollection):
                v.freeze()


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

    def is_field_edited(self, field : str) -> bool:
        value = self._updates.get(field, None)
        if value is None:
            return False
        return value.edited if isinstance(value, JournalledCollection) else True

    def get_original_field(self, field : str) -> Any:
        if not self.has_field(field):
            raise AttributeError(f"Entity of type {self.entity.__class__.__name__} does not have field '{field}'.")
        return super(Entity, self.entity).__getattribute__(field)

    def _wrap_field(self, field : str, original : Any) -> Any:
        if field in self._updates:
            raise RuntimeError(f"Field '{field}' of journal {self} is already wrapped.")

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

        if self._frozen:
            raise RuntimeError(f"Cannot wrap field '{field}' of frozen journal {self}.")
        self._invalidated = False

        self._updates[field] = new
        self.propagate()

        return new

    def set_field[T](self, field : str, value : T) -> T:
        if self._frozen:
            raise RuntimeError(f"Cannot modify field '{field}' of frozen journal {self}.")
        self._invalidated = False

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

        self._reset_children_uids_cache()
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

    def on_journalled_collection_edit(self, collection : JournalledCollection) -> None:
        if self._frozen:
            raise RuntimeError(f"Cannot modify field '{collection.instance_name}' of frozen journal {self}.")

        self._reset_children_uids_cache()
        self._invalidated = False

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
        if self._frozen:
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

                if nm not in self._updates:
                    value = self._wrap_field(nm, value)
                assert isinstance(value, JournalledOrderedViewSet)

                self.log.debug("Invalidating OrderedViewSet field '%s' of journal %s due to invalidation of dependency %s", nm, self, source.entity)
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

        if not self.dirty:
            return

        for dep in self.entity.dependent_uids:
            entity = Entity.by_uid(dep)

            if not entity.marked_for_deletion:
                entity.on_dependency_invalidated(self)

    def commit(self) -> Entity:
        assert self._invalidated
        self.freeze()

        if not self.dirty:
            self.mark_superseded()
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



    # MARK: Children
    def iter_children_uids(self) -> Iterable[Uid]:
        yield from self.entity.iter_children_uids(use_journal=True)

    @cached_property
    def children_uids(self) -> Iterable[Uid]:
        return frozenset(self.iter_children_uids())

    def _reset_children_uids_cache(self) -> None:
        self.__dict__.pop('children_uids', None)



    # MARK: Annotations
    @property
    def annotations(self) -> UidProxySet[Annotation]:
        return UidProxySet[Annotation](owner=self, field='annotation_uids')



    # MARK: Dependencies
    @property
    def extra_dependencies(self) -> UidProxySet[Entity]:
        from ..collections.uid_proxy import UidProxySet
        return UidProxySet[Entity](owner=self, field='extra_dependency_uids')

    def add_dependency(self, entity_or_uid : Entity | Uid) -> None:
        uid = Entity.narrow_to_uid(entity_or_uid)
        if uid in self.extra_dependency_uids:
            return
        self.extra_dependency_uids.add(uid)

    def remove_dependency(self, entity_or_uid : Entity | Uid) -> None:
        uid = Entity.narrow_to_uid(entity_or_uid)
        if uid not in self.extra_dependency_uids:
            return
        self.extra_dependency_uids.discard(uid)