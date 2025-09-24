# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref

from pydantic import ConfigDict, Field, PrivateAttr, computed_field, field_validator
from typing import ClassVar, Any, override, TypedDict, Literal, Iterator, Callable
from datetime import datetime
from collections.abc import MutableSet, MutableMapping

from ...util.models import LoggableHierarchicalModel
from ...util.callguard import CallguardClassOptions

from ..models.uid import Uid, IncrementingUidFactory
from ..models.entity.entity import Entity
from ..models.entity.entity_audit_log import EntityAuditType
from ..models.entity.superseded import superseded_check

from .entity_journal import EntityJournal


class SessionParams(TypedDict):
    actor  : str
    reason : str


class Session(LoggableHierarchicalModel):
    __callguard_class_options__ = CallguardClassOptions['Session'](
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

    def _call_parent_hook(self, hook_name: Literal['start'] | Literal['end'] | Literal['apply'] | Literal['commit'] | Literal['abort'], *args: Any, **kwargs: Any) -> None:
        from .session_manager import SessionManager
        parent = self.instance_parent
        if not isinstance(parent, SessionManager):
            raise RuntimeError("Instance parent is not a SessionManager.")
        parent.call_owner_hook(hook_name, self, *args, **kwargs)


    # MARK: Uid
    _UID_FACTORY : ClassVar[IncrementingUidFactory] = IncrementingUidFactory()
    uid : Uid = Field(default_factory=lambda data: Session._UID_FACTORY.next('Session'), validate_default=True, description="Unique identifier for this session.")

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
    _after_invalidate : bool = PrivateAttr(default=False)
    @property
    def in_commit(self) -> bool:
        try:
            return getattr(self, '_in_commit', False)
        except:
            return False

    _in_abort : bool = PrivateAttr(default=False)
    @property
    def in_abort(self) -> bool:
        try:
            return getattr(self, '_in_abort', False)
        except:
            return False

    @property
    def superseded(self) -> bool:
        return self.ended


    # MARK: Entities created in this session
    _entities_created : MutableSet[Uid] = PrivateAttr(default_factory=set)

    def on_entity_created(self, entity_or_uid: Entity | Uid) -> None:
        uid = Entity.narrow_to_uid(entity_or_uid)
        entity = Entity.narrow_to_entity(entity_or_uid)

        log = entity.entity_log.most_recent
        if log.what != EntityAuditType.CREATED:
            raise ValueError("Entity was not created, cannot notify session.")
        if log.when < self.start_time:
            raise ValueError("Entity was created before this session started.")

        self._entities_created.add(uid)


    # MARK: Entities deleted in this session
    _entities_deleted : MutableSet[Uid] = PrivateAttr(default_factory=set)

    def mark_entity_for_deletion(self, entity_or_uid: Entity | Uid) -> None:
        uid = Entity.narrow_to_uid(entity_or_uid)
        self._entities_deleted.add(uid)

        journal = self._entity_journals.pop(uid, None)
        if journal is not None:
            journal.mark_invalid()

    def is_entity_marked_for_deletion(self, entity_or_uid: Entity | Uid) -> bool:
        uid = Entity.narrow_to_uid(entity_or_uid)
        return uid in self._entities_deleted



    # MARK: Entity Journals
    _entity_journals : MutableMapping[Uid, EntityJournal] = PrivateAttr(default_factory=dict)

    @property
    def dirty(self) -> bool:
        return (
            any(j.dirty for j in self._entity_journals.values()) or
            bool(self._entities_created) or
            bool(self._entities_deleted)
        )

    def _add_entity_journal(self, entity: Entity) -> EntityJournal | None:
        if self.ended:
            raise RuntimeError("Cannot add an entity journal to an ended session.")

        if self._after_invalidate or self._in_abort:
            return None

        journal_cls = entity.get_journal_class()
        if not issubclass(journal_cls, EntityJournal):
            raise TypeError(f"{entity.__class__.__name__} journal class {journal_cls} is not a subclass of EntityJournal.")
        journal = journal_cls(entity=entity)
        self._entity_journals[entity.uid] = journal
        return journal

    def get_entity_journal(self, entity: Entity, *, create : bool = True) -> EntityJournal | None:
        if self.ended:
            raise RuntimeError("Cannot get an entity journal from an ended session.")

        if entity.superseded:
            return None

        if entity.uid in self._entities_deleted:
            return None

        journal = self._entity_journals.get(entity.uid, None)
        if journal is not None:
            if journal.entity is not entity:
                if not journal.entity.superseded:
                    raise RuntimeError("Entity journal already exists for a different version of this entity. Use the latest version instead.")
                if create:
                    del self._entity_journals[entity.uid]
            else:
                return journal

        if create:
            return self._add_entity_journal(entity)
        else:
            return None

    def _clear_journals(self) -> None:
        for j in self._entity_journals.values():
            j.mark_invalid()

        self._entity_journals.clear()

    def _clear(self) -> None:
        self._clear_journals()
        self._entities_created.clear()
        self._entities_deleted.clear()

    def contains(self, uid: Uid) -> bool:
        return (
            (uid in self._entity_journals) or
            (uid in self._entities_created) or
            (uid in self._entities_deleted)
        )

    def __len__(self) -> int:
        return len(self._entity_journals) + len(self._entities_created) + len(self._entities_deleted)


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
        self._clear()
        self._call_parent_hook('commit')
        self._in_commit = False

        self.log.info("Commit concluded.")

    def abort(self) -> None:
        if self.ended:
            raise RuntimeError("Cannot abort an ended session.")

        # No need to do anything if there are no edits to commit
        if not self.dirty:
            return

        # TODO: Log abort
        self.log.debug("Aborting session...")
        self._in_abort = True

        # Forcefully delete any entities created in this session
        if self._entities_created:
            self._clear_journals()
            entities = set()

            for uid in self._entities_created:
                entity = Entity.by_uid_or_none(uid)
                if entity is None or entity.superseded:
                    continue
                entities.add(entity)
                if not entity.marked_for_deletion:
                    entity.delete()

            for entity in entities:
                entity.apply_deletion()

        self._clear()
        self.log.debug("Session aborted.")
        self._call_parent_hook('abort')
        self._in_abort = False

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
        self._commit_invalidate()
        self._after_invalidate = True
        self._commit_apply()
        self._commit_deletions()

    def _commit_announce_deletions(self) -> None:
        """
        Announce deletions to dependents, which may in turn mark themselves for deletion.
        """
        self.log.debug("Announcing entity deletions...")

        announced = set()

        while True:
            deletions = list(self._entities_deleted)
            len_deletions = len(deletions)

            for uid in self._entities_deleted:
                if uid in announced:
                    continue

                self.log.debug(f"Announcing deletion of entity {uid}...")
                entity = uid.entity

                for dep in entity.dependents:
                    if not dep.marked_for_deletion:
                        dep.on_dependency_deleted(entity)

                announced.add(uid)

                if (new_len := len(self._entities_deleted)) != len_deletions:
                    # New deletions were added during announcement, restart
                    break
            else:
                break

    def _commit_travel_hierarchy(self, condition : Callable[[EntityJournal], bool]) -> Iterator[EntityJournal]:
        for ej in self._entity_journals.values():
            for inv in ej.commit_yield_hierarchy(condition):
                yield inv

    def _commit_invalidate(self):
        """
        Invalidate all computed fields in all journals.
        """
        self.log.debug("Invalidating all entities with a journal...")

        len_journals = len(self._entity_journals)

        while True:
            for ej in self._commit_travel_hierarchy(lambda x: not x.invalidated):
                self.log.debug(f"Invalidating entity journal for {ej.entity.instance_name}...")
                ej.invalidate()

                if (new_len := len(self._entity_journals)) != len_journals:
                    # New journals were added during invalidation, restart
                    len_journals = new_len
                    break
            else:
                break

    def _commit_apply(self) -> None:
        """
        Iterate through flattened hierarchy, flatten updates and apply them (creating new entity versions).
        Where an entity holds references to child entities (e.g. lists/dicts), these references are refreshed.
        """
        self.log.debug("Committing journals...")

        for journal in self._commit_travel_hierarchy(lambda x: not x.superseded):
            self.log.debug(f"Committing entity journal for {journal.entity_uid}...")
            journal.commit()

        self._call_parent_hook('apply')

    def _commit_deletions(self) -> None:
        """
        Apply deletions to all entities marked for deletion.
        """
        self.log.debug("Applying entity deletions...")

        for uid in self._entities_deleted:
            self.log.debug(f"Applying deletion to Entity {uid}...")
            entity = uid.entity
            entity.apply_deletion()