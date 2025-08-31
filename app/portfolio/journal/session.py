# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import ConfigDict, Field, PrivateAttr, computed_field
from typing import ClassVar, Any, override, TypedDict
from datetime import datetime

from ...util.mixins import LoggableHierarchicalModel, NamedProtocol
from ...util.helpers.callguard import callguard_class

from ..models.uid import Uid, IncrementingUidFactory
from ..models.entity.entity import Entity
from ..models.entity.superseded import superseded_check

from .entity_journal import EntityJournal


class SessionParams(TypedDict):
    actor  : str
    reason : str


@callguard_class(decorator=superseded_check, decorate_public_methods=True, decorate_ignore_patterns=('superseded','ended'))
class Session(LoggableHierarchicalModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        validate_assignment=True,
    )

    # MARK: Uid
    _UID_FACTORY : ClassVar[IncrementingUidFactory] = IncrementingUidFactory()
    uid : Uid = Field(default_factory=lambda data: Session._UID_FACTORY.next('Session'), validate_default=True, description="Unique identifier for this session.")

    @computed_field
    @property
    def instance_name(self) -> str:
        return str(self.uid)


    # MARK: Metadata
    actor  : str = Field(description="Identifier or name of the actor responsible for this session.")
    reason : str = Field(description="Reason for starting this session.")
    start_time : datetime = Field(default_factory=datetime.now, init=False, description="Timestamp when the session started.")


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
        return self.ended


    # MARK: State machine
    @override
    def model_post_init(self, context : Any):
        super().model_post_init(context)

        self._start()

    def _start(self) -> None:
        # TODO: Log start
        self.log.info("Starting session.")

    def commit(self) -> None:
        if self.ended:
            raise RuntimeError("Cannot commit an ended session.")

        # No need to do anything if there are no edits to commit
        if not self.dirty:
            return

        # TODO: Log commit
        self.log.info("Committing session.")

        raise NotImplementedError("Session commit not implemented yet.")

    def abort(self) -> None:
        if self.ended:
            raise RuntimeError("Cannot abort an ended session.")

        # No need to do anything if there are no edits to commit
        if not self.dirty:
            return

        # TODO: Log abort

        self._clear()

    def end(self) -> None:
        if self.ended:
            raise RuntimeError("Cannot end an already ended session.")

        if self.dirty:
            self.commit()

        # TODO: Log ended

        self._ended = True


    # Entity Journals
    _entity_journals : dict[Uid, EntityJournal] = PrivateAttr(default_factory=dict)

    @property
    def dirty(self) -> bool:
        return any(j.dirty for j in self._entity_journals.values())

    def _add_entity_journal(self, entity: Entity) -> EntityJournal:
        if self.ended:
            raise RuntimeError("Cannot add an entity journal to an ended session.")

        journal = EntityJournal(entity_uid=entity.uid)
        self._entity_journals[entity.uid] = journal
        return journal

    def get_entity_journal(self, *, uid : Uid | None = None, entity: Entity | None = None) -> EntityJournal:
        if self.ended:
            raise RuntimeError("Cannot get an entity journal from an ended session.")

        if uid is None and entity is None:
            raise ValueError("Either 'uid' or 'entity' must be provided to get an entity journal.")

        if uid is None and entity is not None:
            uid = entity.uid
        if uid is None:
            raise ValueError("Could not determine 'uid' from provided 'entity'.")

        journal = self._entity_journals.get(uid, None)
        if journal is not None:
            return journal

        if entity is None:
            entity = Entity.by_uid(uid)
        if entity is None:
            raise ValueError(f"No entity found with UID '{uid}' to create a journal.")
        return self._add_entity_journal(entity)

    def _clear(self):
        self._entity_journals.clear()

    def contains(self, uid: Uid) -> bool:
        return uid in self._entity_journals

    def __len__(self) -> int:
        return len(self._entity_journals)
