# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import ConfigDict, Field, PrivateAttr, computed_field, BaseModel, ModelWrapValidatorHandler, ValidationInfo, model_validator, PositiveInt, model_validator
from typing import Any, Literal, TYPE_CHECKING, ClassVar
from enum import Enum

from abc import ABCMeta
from collections.abc import Sequence, Mapping, Set

from ...util.mixins import LoggableHierarchicalModel
from ...util.helpers.callguard import callguard_class

from ..models.uid import Uid

from ..models.entity.entity import Entity
from ..models.entity.superseded import superseded_check

from .journalled_sequence import JournalledSequence
from .journalled_mapping import JournalledMapping


@callguard_class(decorator=superseded_check, decorate_public_methods=True, decorate_ignore_patterns=('ended','superseded'))
class EntityJournal(LoggableHierarchicalModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        validate_assignment=True,
    )

    PROPAGATE_TO_CHILDREN : ClassVar[bool] = False


    # MARK: Entity
    entity_uid : Uid = Field(description="Unique identifier of the entity associated with this journal entry.")

    @model_validator(mode='after')
    def _validate_entity_uid(self, info: ValidationInfo) -> 'EntityJournal':
        self.entity # property access fails if the UID is invalid
        return self

    @computed_field(description="The entity associated with this journal entry.")
    @property
    def entity(self) -> Entity:
        if (entity := Entity.by_uid(self.entity_uid)) is None:
            raise ValueError(f"EntityJournal.entity_uid '{self.entity_uid}' does not correspond to a valid Entity.")
        return entity

    @entity.setter
    def entity(self, value : Entity) -> None:
        self.entity_uid = value.uid


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
        for attr, value in self._updates.items():
            # TODO: set
            if isinstance(value, (JournalledSequence, JournalledMapping)):
                if value.edited:
                    return True
            else:
                return True
        return False


    # MARK: Fields API
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
        # TODO: loop through updates and flatten into an updates dict:
        # - if Entity, get latest version (assert version has changed)
        # - if JournalledList / JournalledDict, flatten and make immutable
        #
        # Finally update entity with updates dict and return new entity
        raise NotImplementedError("EntityJournal commit not implemented yet.")