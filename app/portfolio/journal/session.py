# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref

from pydantic import ConfigDict, Field, PrivateAttr, computed_field, field_validator
from typing import ClassVar, Any, override, TypedDict, Literal
from datetime import datetime
from ordered_set import OrderedSet

from ...util.mixins import LoggableHierarchicalModel
from ...util.callguard import CallguardClassOptions

from ..models.uid import Uid, IncrementingUidFactory
from ..models.entity.entity import Entity
from ..models.entity.superseded import superseded_check

from .entity import EntityJournal


class SessionParams(TypedDict):
    actor  : str
    reason : str


class JournalSession(LoggableHierarchicalModel):
    __callguard_class_options__ = CallguardClassOptions['JournalSession'](
        decorator=superseded_check,
        decorate_public_methods=True,
        decorate_ignore_patterns=('superseded','ended'),
    )

    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        validate_assignment=True,
    )

    # MARK: Instance Parent
    @field_validator('instance_parent_weakref', mode='before')
    def _validate_instance_parent_is_session_manager(cls, v: Any) -> Any:
        from .session_manager import SessionManager
        obj = v() if isinstance(v, weakref.ref) else v
        if obj is None or not isinstance(obj, SessionManager):
            raise TypeError("Session parent must be a SessionManager object")
        return v

    def _call_parent_hook(self, hook_name: Literal['start'] | Literal['end'] | Literal['commit'] | Literal['abort'], *args: Any, **kwargs: Any) -> None:
        from .session_manager import SessionManager
        parent = self.instance_parent
        if not isinstance(parent, SessionManager):
            raise RuntimeError("Instance parent is not a SessionManager.")
        parent.call_owner_hook(hook_name, self, *args, **kwargs)


    # MARK: Uid
    _UID_FACTORY : ClassVar[IncrementingUidFactory] = IncrementingUidFactory()
    uid : Uid = Field(default_factory=lambda data: JournalSession._UID_FACTORY.next('JournalSession'), validate_default=True, description="Unique identifier for this session.")

    @computed_field(description="A human-readable name for this session, derived from its UID.")
    @property
    def instance_name(self) -> str:
        return str(self.uid)


    # MARK: Metadata
    actor  : str = Field(description="Identifier or name of the actor responsible for this session.")
    reason : str = Field(description="Reason for starting this session.")
    start_time : datetime = Field(default_factory=datetime.now, init=False, description="Timestamp when the session started.")


    # MARK: State
    _ended : bool = PrivateAttr(default=False)
    @property
    def ended(self) -> bool:
        try:
            return getattr(self, '_ended', False)
        except:
            return False

    _in_commit : bool = PrivateAttr(default=False)
    @property
    def in_commit(self) -> bool:
        try:
            return getattr(self, '_in_commit', False)
        except:
            return False

    @property
    def superseded(self) -> bool:
        return self.ended


    # MARK: Entity Journals
    _entity_journals : dict[Uid, EntityJournal] = PrivateAttr(default_factory=dict)

    @property
    def dirty(self) -> bool:
        return any(j.dirty for j in self._entity_journals.values())

    def _add_entity_journal(self, entity: Entity) -> EntityJournal | None:
        if self.ended:
            raise RuntimeError("Cannot add an entity journal to an ended session.")

        if self._in_commit:
            return None

        journal = EntityJournal(entity=entity)
        self._entity_journals[entity.uid] = journal
        return journal

    def get_entity_journal(self, entity: Entity) -> EntityJournal | None:
        if self.ended:
            raise RuntimeError("Cannot get an entity journal from an ended session.")

        if entity.superseded:
            return None

        journal = self._entity_journals.get(entity.uid, None)
        if journal is not None:
            if journal.entity is not entity:
                if not journal.entity.superseded:
                    raise RuntimeError("Entity journal already exists for a different version of this entity. Use the latest version instead.")
                del self._entity_journals[entity.uid]
            else:
                return journal

        return self._add_entity_journal(entity)

    def _clear(self):
        self._entity_journals.clear()

    def contains(self, uid: Uid) -> bool:
        return uid in self._entity_journals

    def __len__(self) -> int:
        return len(self._entity_journals)


    # MARK: State machine
    @override
    def model_post_init(self, context : Any):
        super().model_post_init(context)

        self._start()

    def _start(self) -> None:
        # TODO: Log start
        self.log.info("Starting session.")
        self._call_parent_hook('start')

    def commit(self) -> None:
        if self.ended:
            raise RuntimeError("Cannot commit an ended session.")

        # No need to do anything if there are no edits to commit
        if not self.dirty:
            return

        # TODO: Log commit
        self.log.info("Committing session...")

        self._in_commit = True
        self._commit()
        self._in_commit = False

        self._clear()
        self.log.info("Commit concluded.")
        self._call_parent_hook('commit')

    def abort(self) -> None:
        if self.ended:
            raise RuntimeError("Cannot abort an ended session.")

        # No need to do anything if there are no edits to commit
        if not self.dirty:
            return

        # TODO: Log abort

        self._clear()
        self.log.debug("Commit aborted.")
        self._call_parent_hook('abort')

    def end(self) -> None:
        if self.ended:
            raise RuntimeError("Cannot end an already ended session.")

        if self.dirty:
            self.commit()

        # TODO: Log ended

        self._ended = True
        self.log.debug("Session ended.")
        self._call_parent_hook('end')


    # MARK: Commit
    def _commit(self) -> None:
        flattened = self._commit_flatten()
        self._commit_apply(flattened)
        self._call_parent_hook('commit')

    def _commit_flatten(self) -> OrderedSet[EntityJournal]:
        """
        Recursively travel the entity journal hierarchy, flattening it into a list of journals such that all dependencies are handled before dependents.
        """
        #self.log.debug("Flattening entity journal hierarchy for commit...")

        journals = OrderedSet([])

        for ej in self._entity_journals.values():
            ej.flatten_hierarchy(journals)

        return journals

    def _commit_apply(self, flattened : OrderedSet[EntityJournal]) -> None:
        """
        Iterate through flattened hierarchy, flatten updates and apply them (creating new entity versions).
        Where an entity holds references to child entities (e.g. lists/dicts), these references are refreshed.
        """
        self.log.debug(f"Committing flattened hierarchy: ({', '.join(str(j.entity) for j in flattened)})")

        entity = None
        for journal in flattened:
            journal.commit()