# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import ConfigDict, Field, PrivateAttr, computed_field, BaseModel, ModelWrapValidatorHandler, ValidationInfo, model_validator, PositiveInt
from typing import Any, Literal, TYPE_CHECKING
from enum import Enum

from abc import ABCMeta
from collections.abc import Sequence, Mapping

from ...util.mixins import LoggableHierarchicalModel
from ...util.helpers.callguard import callguard_class

from ..models.uid import Uid

from ..models.entity.entity import Entity

from .journalled_sequence import JournalledSequence
from .journalled_mapping import JournalledMapping


@callguard_class()
class EntityJournal(LoggableHierarchicalModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        validate_assignment=True,
    )

    entity : 'Entity' = Field(description="Entity associated with this journal entry.")
    version : PositiveInt = Field(default=1, description="Version of the entity at the time of this journal entry.")

    @computed_field(description="Unique identifier of the entity associated with this journal entry.")
    @property
    def entity_uid(self) -> Uid:
        return self.entity.uid

    _updates : dict[str, Any] = PrivateAttr(default_factory=dict)
    _dirty_children : set[Uid] = PrivateAttr(default_factory=set)

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

            if new is not original:
                self._updates[field] = new
                return new

        return original

    def commit(self) -> 'Entity':
        # TODO: loop through updates and flatten into an updates dict:
        # - if Entity, get latest version (assert version has changed)
        # - if JournalledList / JournalledDict, flatten and make immutable
        #
        # Finally update entity with updates dict and return new entity
        raise NotImplementedError("EntityJournal commit not implemented yet.")