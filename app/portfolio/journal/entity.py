# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import ConfigDict, Field, PrivateAttr, field_validator, InstanceOf
from typing import Any, TYPE_CHECKING, ClassVar, override, get_origin, get_args
from ordered_set import OrderedSet
import builtins

from collections.abc import Sequence, Mapping, Set

from ...util.mixins import LoggableHierarchicalModel
from ...util.helpers.callguard import CallguardClassOptions

from ..models.uid import Uid

from ..models.entity.entity import Entity
from ..models.entity.superseded import superseded_check

from .collections.sequence import JournalledSequence
from .collections.mapping import JournalledMapping
from .collections.set import JournalledSet


class EntityJournal(LoggableHierarchicalModel):
    __callguard_class_options__ = CallguardClassOptions['EntityJournal'](
        decorator=superseded_check,
        decorate_public_methods=True,
        allow_same_module=True,
        decorate_ignore_patterns=('ended','superseded','dirty','entity_uid')
    )

    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        validate_assignment=True,
    )

    PROPAGATE_TO_CHILDREN : ClassVar[bool] = False


    # MARK: Entity
    entity : InstanceOf[Entity] = Field(description="The entity associated with this journal entry.")

    @property
    def entity_uid(self) -> Uid:
        return self.entity.uid

    @property
    def version(self) -> int:
        return self.entity.version

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
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}:{self.entity!r}>"

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

    def updated(self, field : str) -> bool:
        return field in self._updates

    def get_original_field(self, field : str) -> Any:
        if not self.has_field(field):
            raise AttributeError(f"Entity of type {self.entity.__class__.__name__} does not have field '{field}'.")
        return super(Entity, self.entity).__getattribute__(field)

    def set[T](self, field : str, value : T) -> T:
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
            self._updates[field] = value

        self.propagate()

        return value

    def get(self, field : str) -> Any:
        field = self.entity.resolve_field_alias(field)

        if field in self._updates:
            return self._updates[field]

        original = self.get_original_field(field)

        if not self.is_computed_field(field) and self.can_modify(field):
            new = original
            if isinstance(original, Sequence) and not isinstance(original, (str, bytes)):
                new = JournalledSequence(original)
            elif isinstance(original, Mapping):
                new = JournalledMapping(original)
            # TODO: set
            elif isinstance(original, Set):
                raise NotImplementedError("JournalledSet not implemented yet.")

            return self.set(field, new)

        return original


    # MARK: Propagation
    _dirty_children : 'builtins.set[EntityJournal]' = PrivateAttr(default_factory=builtins.set)
    _propagated_has_updates : bool = PrivateAttr(default=False)

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
        #self.log.debug("Propagate: entity=%s dirty=%s", self.entity, self.dirty)

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
                continue

            origin = get_origin(annotation)
            if origin is None:
                continue
            if not isinstance(origin, type):
                continue

            args = get_args(annotation)

            if issubclass(origin, Sequence):
                self.log.debug("Refreshing entity sequence '%s'", attr)

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
                self.log.debug("Refreshing entity mapping '%s'", attr)

                if len(args) != 2 or not issubclass(args[1], Entity):
                    continue

                if issubclass(args[0], Uid):
                    for dirty in self._dirty_children:
                        uid = dirty.entity_uid
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
                            field[key] = entity.superseding

            elif issubclass(origin, Set):
                self.log.debug("Refreshing entity set '%s'", attr)

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

        #self.log.debug("Committing journal for entity %s", self.entity)

        # Trigger entity refresh
        self._refresh_entity_collections()

        # Collect all updates
        updates = {}

        for attr, update in self._updates.items():
            if isinstance(update, (JournalledSequence, JournalledMapping, JournalledSet)):
                if not update.edited:
                    continue

            updates[attr] = update

        if not updates:
            return self.entity

        #self.log.debug("Updates to apply to entity %s: %s", self.entity, repr(updates))

        # Update the entity
        new_entity = self._new_entity = self.entity.update(
            **updates
        )

        #self.log.debug("New entity created: %s (v%d)", new_entity, new_entity.version)

        # TODO: How do we handle updating instance_parent when the parent gets superseded?
        #       Maybe propagate the change to all children entities here?
        #       Or maybe entities could catch accesses to instance_parent in __getattr__ and redirect to the most recent version?
        #       ~~What about if the parent's name changed, how do we clear the logger hierarchy cache?~~
        #           UPDATE: Entity.update now fails if the entity name changes during the update

        # Done
        return new_entity