# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref
import itertools

from pydantic import ConfigDict, Field, PrivateAttr, computed_field, field_validator
from typing import ClassVar, Any, override, TypedDict, Literal, Iterable, Callable
from datetime import datetime
from collections.abc import MutableSet, MutableMapping

from ...util.models import LoggableHierarchicalModel
from ...util.callguard import CallguardClassOptions

from ..models.uid import Uid, IncrementingUidFactory, UID_SEPARATOR
from ..models.entity.entity import Entity
from ..models.entity.entity_audit_log import EntityAuditType
from ..models.entity.superseded import superseded_check, SupersededError

from .entity_journal import EntityJournal
from .protocols import SessionManagerHookLiteral


class SessionParams(TypedDict):
    actor  : str
    reason : str


class Session(LoggableHierarchicalModel):
    __callguard_class_options__ = CallguardClassOptions['Session'](
        decorator=superseded_check,
        decorate_public_methods=True,
        decorate_ignore_patterns=('superseded','ended'),
        allow_same_module=True,
        ignore_patterns=('_commit_invalidate_travel_hierarchy_condition', '_commit_apply_travel_hierarchy_condition'),
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

    def _call_parent_hook(self, hook_name: SessionManagerHookLiteral, *args: Any, **kwargs: Any) -> None:
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
        try:
            return str(self.uid)
        except:
            return f"{self.__class__.__name__}{UID_SEPARATOR}<invalid-uid>"


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
    _deletions_announced : MutableSet[Uid] = PrivateAttr(default_factory=set)

    def mark_entity_for_deletion(self, entity_or_uid: Entity | Uid) -> None:
        if self._after_invalidate:
            raise RuntimeError("Cannot mark an entity for deletion after invalidation.")

        uid = Entity.narrow_to_uid(entity_or_uid)
        self._entities_deleted.add(uid)

        journal = self._entity_journals.pop(uid, None)
        if journal is not None:
            journal.mark_superseded()

    def mark_entity_deletion_as_announced(self, entity_or_uid: Entity | Uid) -> None:
        if self._after_invalidate:
            raise RuntimeError("Cannot mark an entity for deletion after invalidation.")

        uid = Entity.narrow_to_uid(entity_or_uid)
        if uid not in self._entities_deleted:
            raise ValueError("Entity is not marked for deletion in this session; cannot mark deletion as announced.")
        self._deletions_announced.add(uid)

    def is_entity_marked_for_deletion(self, entity_or_uid: Entity | Uid) -> bool:
        uid = Entity.narrow_to_uid(entity_or_uid)
        return uid in self._entities_deleted

    def has_entity_deletion_been_announced(self, entity_or_uid: Entity | Uid) -> bool:
        uid = Entity.narrow_to_uid(entity_or_uid)
        return uid in self._deletions_announced



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

        if self._after_invalidate:
            self.log.warning("Cannot add an entity journal after invalidation.")
            return None

        if self._in_abort:
            self.log.warning("Cannot add an entity journal during abort.")
            return None

        journal_cls = entity.get_journal_class()
        if not issubclass(journal_cls, EntityJournal):
            raise TypeError(f"{entity.__class__.__name__} journal class {journal_cls} is not a subclass of EntityJournal.")
        journal = journal_cls(entity=entity)
        self._entity_journals[entity.uid] = journal
        return journal

    def get_entity_journal(self, entity: Entity, *, create : bool = True) -> EntityJournal | None:
        if self.ended:
            raise SupersededError("Cannot get an entity journal from an ended session.")

        if entity.superseded:
            self.log.warning(f"Entity {entity.instance_name} is superseded; cannot create or retrieve journal.")
            return None

        if entity.uid in self._entities_deleted:
            self.log.warning(f"Entity {entity.instance_name} is marked for deletion in this session; cannot create or retrieve journal.")
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
            j.mark_superseded()

        self._entity_journals.clear()

    def _clear(self) -> None:
        self._clear_journals()
        self._entities_created.clear()
        self._entities_deleted.clear()
        self._deletions_announced.clear()

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
            raise SupersededError("Cannot commit an ended session.")

        # No need to do anything if there are no edits to commit
        if not self.dirty:
            return

        # TODO: Log commit
        self.log.info("Committing session...")

        self._in_commit = True
        try:
            self._commit()
            self._clear()
            self._call_parent_hook('commit')
        finally:
            self._in_commit = False
            self._after_invalidate = False

        self.log.info("Commit concluded.")

    def abort(self) -> None:
        if self.ended:
            raise RuntimeError("Cannot abort an ended session.")

        # No need to do anything if there are no edits to commit
        if not self.dirty:
            return

        # TODO: Log abort
        self.log.warning("Aborting session...")
        self._in_abort = True

        try:
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
            self.log.warning("Session aborted.")
            self._call_parent_hook('abort')
        finally:
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
        self._commit_apply()
        self._commit_deletions()

    def _commit_travel_hierarchy(self, iterable : Iterable[Uid], *, condition : Callable[[Entity], bool] | None = None, copy : bool = False) -> Iterable[Entity]:
        if copy:
            iterable = list(iterable)
        for uid in iterable:
            yield from uid.entity.iter_hierarchy(condition=condition, use_journal=True)

    def _commit_invalidate_travel_hierarchy_condition(self, e: Entity) -> bool:
        j = self._entity_journals.get(e.uid, None)
        if j is not None:
            return not j.invalidated
        elif e.uid in self._entities_deleted:
            return e.uid not in self._deletions_announced
        else:
            return False

    def _commit_invalidate(self):
        """
        Invalidate all computed fields in all journals.
        """
        self.log.debug("Invalidating all entities with a journal or that have been deleted...")

        len_journals = len(self._entity_journals )
        len_deleted  = len(self._entities_deleted)

        def should_restart() -> bool:
            nonlocal len_journals, len_deleted

            new_len_journals = len(self._entity_journals )
            new_len_deleted  = len(self._entities_deleted)
            restart = (new_len_journals != len_journals) or (new_len_deleted != len_deleted)

            if restart:
                len_journals = new_len_journals
                len_deleted  = new_len_deleted
            return restart

        pass_count = 0
        while True:
            pass_count += 1
            self.log.debug(t"Starting invalidation pass {pass_count}...")

            finished = False
            for e in self._commit_travel_hierarchy(
                itertools.chain(self._entities_deleted, self._entity_journals.keys()),
                condition=self._commit_invalidate_travel_hierarchy_condition,
                copy=True
            ):
                if e.uid in self._entities_deleted:
                    self.log.debug(t"Announcing deletion of entity {e!s}...")
                    assert e.uid not in self._deletions_announced
                    e.announce_deletion()
                    self._deletions_announced.add(e.uid)
                else:
                    self.log.debug(t"Invalidating entity {e!s}...")
                    j = self._entity_journals[e.uid]
                    j.invalidate()

                if should_restart():
                    break
            else:
                finished = True
            if not finished:
                continue

            self._call_parent_hook('invalidate')
            if not should_restart():
                break

        assert self._deletions_announced >= (self._entities_deleted)
        assert all(j.invalidated for j in self._entity_journals.values())

        self._after_invalidate = True


    def _commit_apply_travel_hierarchy_condition(self, e: Entity) -> bool:
        j = self._entity_journals.get(e.uid, None)
        if j is None or j.superseded:
            return False
        return True

    def _commit_apply(self) -> None:
        """
        Iterate through flattened hierarchy, flatten updates and apply them (creating new entity versions).
        Where an entity holds references to child entities (e.g. lists/dicts), these references are refreshed.
        """
        self.log.debug("Committing journals...")

        for e in self._commit_travel_hierarchy(
            self._entity_journals.keys(),
            condition=self._commit_apply_travel_hierarchy_condition,
            copy=False
        ):
            self.log.debug(f"Committing entity {e.uid}...")
            j = self._entity_journals[e.uid]
            j.commit()

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