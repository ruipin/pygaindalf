# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import ConfigDict, Field, PrivateAttr, computed_field, BaseModel, ModelWrapValidatorHandler, ValidationInfo, model_validator, PositiveInt
from typing import Any, Literal, TYPE_CHECKING
from enum import Enum

from abc import ABCMeta
from collections.abc import Sequence, Mapping, Set

from ...util.mixins import LoggableHierarchicalModel
from ...util.helpers.callguard import callguard_class

from ..models.uid import Uid

from ..models.entity.entity import Entity
from ..models.entity.stale import stale_check

from .journalled_sequence import JournalledSequence
from .journalled_mapping import JournalledMapping




@callguard_class()
class EntityJournal(LoggableHierarchicalModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        validate_assignment=True,
    )


    # MARK: Entity
    entity : 'Entity' = Field(description="Entity associated with this journal entry.")

    @computed_field(description="Unique identifier of the entity associated with this journal entry.")
    @property
    def entity_uid(self) -> Uid:
        return self.entity.uid

    _updates : dict[str, Any] = PrivateAttr(default_factory=dict)
    _dirty_children : set[Uid] = PrivateAttr(default_factory=set)


    # MARK: Stale
    _ended : bool = PrivateAttr(default=False)
    @property
    def ended(self) -> bool:
        return self._ended

    @property
    def superseded(self) -> bool:
        return self.entity.superseded

    @property
    def stale(self) -> bool:
        return self.ended or self.superseded

    @property
    @stale_check
    def dirty(self) -> bool:
        for attr, value in self._updates.items():
            # TODO: set
            if isinstance(value, (JournalledSequence, JournalledMapping)):
                if value.edited:
                    return True
            else:
                return True
        return False


    # MARK: Fields API
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

    def get(self, field : str) -> Any:
        if field in self._updates:
            return self._updates[field]

        original = self.get_original_field(field)

        if not self.is_computed_field(field):
            new = original
            if isinstance(original, Sequence):
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


    # MARK: Commit
    def commit(self) -> 'Entity':
        if self.stale:
            raise RuntimeError("Cannot commit a stale journal.")

        # TODO: loop through updates and flatten into an updates dict:
        # - if Entity, get latest version (assert version has changed)
        # - if JournalledList / JournalledDict, flatten and make immutable
        #
        # Finally update entity with updates dict and return new entity
        raise NotImplementedError("EntityJournal commit not implemented yet.")