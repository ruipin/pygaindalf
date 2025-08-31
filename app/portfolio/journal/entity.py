# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import ConfigDict, Field, PrivateAttr, computed_field, BaseModel, ModelWrapValidatorHandler, ValidationInfo, model_validator, PositiveInt, model_validator, field_validator
from typing import Any, Literal, TYPE_CHECKING, ClassVar, override, get_origin, get_args
from enum import Enum
from ordered_set import OrderedSet
import builtins

from abc import ABCMeta
from collections.abc import Sequence, Mapping, Set

from ...util.mixins import LoggableHierarchicalModel
from ...util.helpers.callguard import callguard_class

from ..models.uid import Uid

from ..models.entity.entity import Entity
from ..models.entity.superseded import superseded_check

from .collections.sequence import JournalledSequence
from .collections.mapping import JournalledMapping
from .collections.set import JournalledSet


@callguard_class(decorator=superseded_check, decorate_public_methods=True, allow_same_module=True, decorate_ignore_patterns=('ended','superseded','dirty'))
class EntityJournal(LoggableHierarchicalModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        validate_assignment=True,
    )

    PROPAGATE_TO_CHILDREN : ClassVar[bool] = False


    # MARK: Entity
    entity : Entity = Field(description="The entity associated with this journal entry.")

    @property
    def entity_uid(self) -> Uid:
        return self.entity.uid

    @property
    def version(self) -> int:
        return self.entity.version

    @override
    def __hash__(self) -> int:
        return hash((self.__class__.__name__, hash(self.entity)))

    # We use a plain validator here as we do not want pydantic to recursively validate the entity - that would cause an infinite loop
    @field_validator('entity', mode='plain')
    def _validate_entity(entity : Any) -> Entity:
        if not isinstance(entity, Entity):
            raise TypeError(f"Expected Entity, got {type(entity).__name__}")

        if entity.superseded:
            raise ValueError(f"EntityJournal.entity '{entity}' is superseded.")

        return entity


    # MARK: Superseded
    _ended : bool = PrivateAttr(default=False)
    @property
    def ended(self) -> bool:
        try:
            return getattr(self, '_ended', False)
        except:
            return False

    @property
    def superseded(self) -> bool:
        return self.ended or self.entity.superseded

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

    def is_computed_field(self, field : str) -> bool:
        return field in self.entity.__class__.model_computed_fields

    def has_field(self, field : str) -> bool:
        # TODO: Should we use hasattr instead?
        return field in self.entity.__class__.model_fields or self.is_computed_field(field)

    def get_original_field(self, field : str) -> Any:
        if not self.has_field(field):
            raise AttributeError(f"Entity of type {self.entity.__class__.__name__} does not have field '{field}'.")
        return super(Entity, self.entity).__getattribute__(field)

    def set(self, field : str, value : Any) -> None:
        has_update = field in self._updates
        if not has_update and not self.has_field(field):
            raise AttributeError(f"Entity of type {self.entity.__class__.__name__} does not have field '{field}'.")

        original = self.get_original_field(field)
        if value is original:
            if has_update:
                del self._updates[field]
        else:
            self._updates[field] = value

        self.propagate()

    def get(self, field : str) -> Any:
        if field in self._updates:
            return self._updates[field]

        original = self.get_original_field(field)

        if not self.is_computed_field(field):
            new = original
            if isinstance(original, Sequence) and not isinstance(original, (str, bytes)):
                new = JournalledSequence(original)
            elif isinstance(original, Mapping):
                new = JournalledMapping(original)
            # TODO: set
            elif isinstance(original, Set):
                raise NotImplementedError("JournalledSet not implemented yet.")

            if new is not original:
                self._updates[field] = new
                return new

        return original


    # MARK: Propagation
    _dirty_children : 'builtins.set[EntityJournal]' = PrivateAttr(default_factory=builtins.set)
    _propagated_dirty : bool = PrivateAttr(default=False)

    def _update_child_dirty_state(self, child : 'EntityJournal', dirty : bool | None = None):
        if dirty is None:
            dirty = child.dirty

        if dirty:
            self._dirty_children.add(child)
        else:
            self._dirty_children.discard(child)

        self.propagate()

    def propagate(self) -> None:
        """
        Propagate whether we are dirty to the parent entity's journal
        """
        # Check if the dirty state has changed since the last time we propagated to our parent journal
        dirty = self.dirty
        if dirty == self._propagated_dirty:
            return

        # Propagate to parent journal
        parent = self.entity.instance_parent
        if parent is None:
            return
        if not isinstance(parent, Entity):
            raise TypeError("EntityJournal can only propagate when the parent is an Entity.")

        parent_journal = parent.journal
        parent_journal._update_child_dirty_state(self, dirty)

        # Cache the last propagated dirty state
        self._propagated_dirty = dirty


    # MARK: Commit
    _new_entity : Entity | None = PrivateAttr(default=None)

    def flatten_hierarchy(self, journals : 'OrderedSet[EntityJournal]') -> None:
        """
        Return a flat ordered set of all journals in this hierarchy
        """
        if self in journals:
            return

        # Iterate dirty children journals
        for child in self._dirty_children:
            # If the journal already exists in the set, we can skip it
            if child in journals:
                continue

            child.flatten_hierarchy(journals)

        if self.entity_uid in journals:
            raise RuntimeError(f"Journal {self} was added to the flattened hierarchy by one of its children. This should not happen.")

        # Add self, then return
        journals.add(self)

    def _refresh_entity_collections(self):
        # No need to do an entity refresh if there are no dirty children
        if not self._dirty_children:
            return

        # If our entity contains collections of Entities, we need to ensure they are also updated
        for attr, info in self.entity.__class__.model_fields.items():
            field = self.get(attr)
            if field is None:
                continue

            annotation = info.annotation
            if annotation is None:
                self.log.warning(f"Entity field '{attr}' has no annotation. Skipping entity refresh.")
                continue

            origin = get_origin(annotation)
            if origin is None:
                self.log.warning(f"Entity field '{attr}' has no origin. Skipping entity refresh.")
                continue

            args = get_args(annotation)

            if issubclass(origin, Sequence):
                if len(args) != 1 or not issubclass(args[0], Entity):
                    self.log.warning(f"Entity field '{attr}' is annotated as a sequence but the item type is not an Entity. Skipping entity refresh.")
                    continue

                for i, entity in enumerate(field):
                    if not isinstance(entity, Entity):
                        raise TypeError(f"Entity field '{attr}' is annotated as a sequence of Entities but the update contains a non-Entity item.")
                    if entity.superseded:
                        superseding = entity.superseding
                        if superseding is None:
                            raise RuntimeError(f"Entity field '{attr}' contains an entity '{entity}' that is marked as superseded but has no superseding entity.")
                        else:
                            field[i] = superseding

            elif issubclass(origin, Mapping):
                if len(args) != 2 or not issubclass(args[1], Entity):
                    continue

                if issubclass(args[1], Uid):
                    for dirty in self._dirty_children:
                        if dirty.entity_uid in field:
                            superseding = dirty.entity.superseding
                            if superseding is None:
                                del field[dirty.entity_uid]
                            else:
                                field[dirty.entity_uid] = superseding
                else:
                    for key, entity in field.items():
                        if not isinstance(entity, Entity):
                            raise TypeError(f"Field '{attr}' is annotated as a mapping of Entities but the update contains a non-Entity item.")
                        if entity.superseded:
                            field[key] = entity.entity_log.most_recent

            elif issubclass(origin, Set):
                if len(args) != 1 or not issubclass(args[0], Entity):
                    continue

                for item in field:
                    if not isinstance(item, Entity):
                        raise TypeError(f"Field '{attr}' is annotated as a set of Entities but the update contains a non-Entity item.")
                    if item.superseded:
                        field.discard(item)
                        superseding = item.superseding
                        if superseding is not None:
                            field.add(superseding)

    def commit(self) -> Entity:
        if not self.dirty:
            return self.entity

        # Trigger entity refresh
        self._refresh_entity_collections()

        # Collect all updates
        updates = {}

        for attr, update in self._updates.items():
            if isinstance(update, (JournalledSequence, JournalledMapping, JournalledSet)):
                if not update.edited:
                    continue

            # TODO: Do we need to convert journalled collections to their original form or is pydantic smart enough to coerce them to the proper type?
            updates[attr] = update

        if not updates:
            return self.entity

        # Update the entity
        new_entity = self._new_entity = self.entity.update(
            **updates
        )

        # TODO: How do we handle updating instance_parent when the parent gets superseded?
        #       Maybe propagate the change to all children entities here?
        #       Or maybe entities could catch accesses to instance_parent in __getattr__ and redirect to the most recent version?
        #       ~~What about if the parent's name changed, how do we clear the logger hierarchy cache?~~
        #           UPDATE: Entity.update now fails if the entity name changes during the update

        # Done
        return new_entity