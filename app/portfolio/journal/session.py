# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime
import sys
import weakref

from collections.abc import Callable, Iterable, MutableMapping, MutableSet, Sequence
from typing import TYPE_CHECKING, Any, ClassVar, NotRequired, TypedDict, Unpack, override

from pydantic import ConfigDict, Field, PrivateAttr, computed_field, field_validator

from ...util.callguard import CallguardClassOptions
from ...util.models import LoggableHierarchicalModel
from ...util.models.superseded import SupersededError, superseded_check
from ...util.models.uid import UID_SEPARATOR, IncrementingUidFactory, Uid, UidProtocol
from ..models.entity import Entity, EntityModificationType, EntityRecord
from .journal import Journal


if TYPE_CHECKING:
    from .protocols import SessionManagerHookLiteral


class AbortOptions(TypedDict):
    exit_on_exception: NotRequired[bool]


class CommitOptions(TypedDict):
    exit_on_exception: NotRequired[bool]


class SessionOptions(TypedDict):
    actor: str
    reason: str
    exit_on_exception: NotRequired[bool]


class Session(LoggableHierarchicalModel):
    __callguard_class_options__ = CallguardClassOptions["Session"](
        decorator=superseded_check,
        decorate_public_methods=True,
        decorate_ignore_patterns=("superseded", "ended"),
        allow_same_module=True,
        ignore_patterns=("_commit_notify_travel_hierarchy_condition", "_commit_apply_travel_hierarchy_condition"),
    )

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )

    # MARK: Instance Parent
    @field_validator("instance_parent_weakref", mode="before")
    def _validate_instance_parent_is_session_manager(cls, v: Any) -> Any:
        from .session_manager import SessionManager

        obj = v() if isinstance(v, weakref.ref) else v
        if obj is None or not isinstance(obj, SessionManager):
            msg = "Session parent must be a SessionManager object"
            raise TypeError(msg)
        return v

    def _call_parent_hook(self, hook_name: SessionManagerHookLiteral, *args: Any, **kwargs: Any) -> None:
        from .session_manager import SessionManager

        parent = self.instance_parent
        if not isinstance(parent, SessionManager):
            msg = "Instance parent is not a SessionManager."
            raise TypeError(msg)
        parent.call_owner_hook(hook_name, self, *args, **kwargs)

    # MARK: Uid
    _UID_FACTORY: ClassVar[IncrementingUidFactory] = IncrementingUidFactory()
    uid: Uid = Field(default_factory=lambda: Session._UID_FACTORY.next("Session"), validate_default=True, description="Unique identifier for this session.")

    @computed_field(description="A human-readable name for this session, derived from its UID.")
    @property
    def instance_name(self) -> str:
        try:
            return str(self.uid)
        except Exception:  # noqa: BLE001 as we want to ensure we can use this in exception messages
            return f"{type(self).__name__}{UID_SEPARATOR}<invalid-uid>"

    # MARK: Metadata
    actor: str = Field(description="Identifier or name of the actor responsible for this session.")
    reason: str = Field(description="Reason for starting this session.")
    start_time: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.UTC), init=False, description="Timestamp when the session started."
    )

    # MARK: Options
    exit_on_exception: bool = Field(default=True, description="Whether to exit the application on exceptions during commit or abort.")

    # MARK: State
    @property
    def superseded(self) -> bool:
        return self.ended

    # MARK: Entities created in this session
    _created: MutableSet[Uid] = PrivateAttr(default_factory=set)

    def on_entity_record_created(self, record_or_uid: EntityRecord | Uid) -> None:
        uid = EntityRecord.narrow_to_uid(record_or_uid)
        record = EntityRecord.narrow_to_instance(record_or_uid)

        log = record.entity_log.most_recent
        if log.what != EntityModificationType.CREATED:
            msg = "EntityRecord was not created, cannot notify session."
            raise ValueError(msg)
        if log.when < self.start_time:
            msg = "EntityRecord was created before this session started."
            raise ValueError(msg)

        self._created.add(uid)

    # MARK: EntityRecord Journals
    _journals: MutableMapping[Uid, Journal] = PrivateAttr(default_factory=dict)

    @property
    def dirty(self) -> bool:
        return any(j.dirty for j in self._journals.values()) or bool(self._created)

    def _add_journal(self, uid: Uid, entity: Entity, record: EntityRecord | None) -> Journal | None:
        assert entity is not None and entity.uid == uid, "Entity is not valid."  # noqa: PT018
        assert record is None or record.uid == uid, "Record is not valid."
        if self.ended:
            msg = "Cannot add an entity journal to an ended session."
            raise RuntimeError(msg)

        if self._after_commit_notify:
            msg = "Cannot add an entity journal after notification phase."
            raise RuntimeError(msg)

        record_type = entity.get_record_type() if record is None else type(record)
        journal_type = record_type.get_journal_class()
        if not issubclass(journal_type, Journal):
            msg = f"{type(record).__name__} journal class {journal_type} is not a subclass of EntityJournal."
            raise TypeError(msg)

        assert uid not in self._journals, "Journal for this UID already exists."
        self._journals[uid] = journal = journal_type(instance_parent=weakref.ref(self), uid=uid)  # pyright: ignore[reportArgumentType]
        assert journal.record_or_none is record, "Journal record does not match."
        assert journal.entity is entity, "Journal entity does not match."

        self._restart_commit_notify = True

        return journal

    def get_journal(self, target: UidProtocol | Uid, *, create: bool = True) -> Journal | None:
        if self.ended:
            msg = "Cannot get an entity journal from an ended session."
            raise SupersededError(msg)

        if isinstance(target, Uid):
            uid = target
        elif isinstance(target, UidProtocol):
            uid = target.uid
        else:
            msg = "Target must be an Entity, EntityRecord or Uid."
            raise TypeError(msg)

        entity = Entity.by_uid(uid)

        journal = self._journals.get(uid, None)
        if journal is not None:
            if journal.version != entity.version:
                assert journal.superseded, "Journal must be superseded here"
                if create:
                    del self._journals[uid]
            else:
                return journal

        if create:
            record = EntityRecord.by_uid_or_none(uid)
            if record is not None and record.superseded:
                self.log.warning(t"EntityRecord {record.instance_name} is superseded; cannot create journal.")
                return None

            return self._add_journal(uid, entity, record)
        else:
            return None

    def _clear_journals(self) -> None:
        for j in self._journals.values():
            j.mark_superseded()

        self._journals.clear()

    def _clear(self) -> None:
        self._clear_journals()
        self._created.clear()

    def contains(self, uid: Uid) -> bool:
        return (uid in self._journals) or (uid in self._created)

    def __len__(self) -> int:
        return len(self._journals) + len(self._created)

    # MARK: Start
    @override
    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)

        self._start()

    def _start(self) -> None:
        # TODO: Log start
        self.log.info(t"Starting session: '{self.reason}' by '{self.actor}'.")
        self._call_parent_hook("start")

    # MARK: Abort
    _in_abort: bool = PrivateAttr(default=False)

    @property
    def in_abort(self) -> bool:
        try:
            return getattr(self, "_in_abort", False)
        except (TypeError, AttributeError, KeyError):
            return False

    def abort(self, **options: Unpack[AbortOptions]) -> None:
        if self.ended:
            msg = "Cannot abort an ended session."
            raise RuntimeError(msg)

        # No need to do anything if there are no edits to commit
        if not self.dirty:
            return

        exit_on_exception = options.get("exit_on_exception", self.exit_on_exception)

        # TODO: Log abort
        self.log.warning("Aborting session...")
        self._in_abort = True

        try:
            # Forcefully delete any entity records created in this session
            if self._created:
                self._clear_journals()

                for uid in self._created:
                    if (entity := Entity.by_uid_or_none(uid)) is not None:
                        entity.revert()

            self._clear()
            self.log.warning("Session aborted.")
            self._call_parent_hook("abort")
        except:
            if exit_on_exception:
                self.log.exception("Exception occurred during session abort; exiting application.")
                sys.exit(1)
            raise
        finally:
            self._in_abort = False

    # MARK: End
    _ended: bool = PrivateAttr(default=False)

    @property
    def ended(self) -> bool:
        try:
            return getattr(self, "_ended", False)
        except (TypeError, AttributeError, KeyError):
            return False

    def end(self) -> None:
        if self.ended:
            msg = "Cannot end an already ended session."
            raise RuntimeError(msg)

        if self.dirty:
            self.commit()

        # TODO: Log ended

        self._ended = True
        self.log.debug("Session ended.")
        self._call_parent_hook("end")

    # MARK: Commit
    _in_commit: bool = PrivateAttr(default=False)
    _after_commit_notify: bool = PrivateAttr(default=False)

    @property
    def in_commit(self) -> bool:
        try:
            return getattr(self, "_in_commit", False)
        except (TypeError, AttributeError, KeyError):
            return False

    def commit(self, **options: Unpack[CommitOptions]) -> None:
        if self.ended:
            msg = "Cannot commit an ended session."
            raise SupersededError(msg)

        # No need to do anything if there are no edits to commit
        if not self.dirty:
            return

        exit_on_exception = options.get("exit_on_exception", self.exit_on_exception)

        # TODO: Log commit
        self.log.debug("Committing session...")

        self._in_commit = True
        try:
            self._commit()
            self._clear()
            self._call_parent_hook("commit")
        except Exception:
            if exit_on_exception:
                self.log.exception("Exception occurred during session commit; exiting application.")
                sys.exit(1)
            raise
        finally:
            self._in_commit = False
            self._after_commit_notify = False

        self.log.debug("Commit concluded.")

    def _commit(self) -> None:
        flattened = self._commit_notify()
        self._commit_apply(flattened)

    def _commit_travel_hierarchy(self, iterable: Iterable[Uid], *, copy: bool = False) -> Iterable[Journal]:
        if copy:
            iterable = list(iterable)

        visited = set()

        def _condition(entity: Entity) -> bool:
            return entity.uid not in visited

        for uid in iterable:
            journal = self._journals.get(uid, None)
            if journal is None or journal.superseded:
                continue

            assert not journal.superseded, "Journal should not be superseded here."

            entity = journal.entity
            for e in entity.iter_hierarchy(condition=_condition, use_journal=True):
                if (j := self._journals.get(e.uid, None)) is not None:
                    assert not j.superseded, "Journal should not be superseded here."
                    yield j
                visited.add(e.uid)

    # MARK: Commit - Notify
    _restart_commit_notify: bool = PrivateAttr(default=False)

    def on_journal_reset_notified_dependents(self, journal: Journal) -> None:  # noqa: ARG002 as this is for overriding
        if not self._in_commit:
            msg = "Can only reset notified dependents during commit."
            raise RuntimeError(msg)
        if self._after_commit_notify:
            msg = "Cannot reset notified dependents after notification phase."
            raise RuntimeError(msg)

        self._restart_commit_notify = True

    def _commit_notify(self) -> Sequence[Journal]:
        """Notify all journals of changes in dependency order, allowing them to update their diffs accordingly."""
        self.log.debug("Notifying journals of changes...")

        flattened = []
        pass_count = 0
        while True:
            pass_count += 1
            flattened.clear()
            self.log.debug(t"Starting notify pass {pass_count}...")

            self._restart_commit_notify = False

            for j in self._commit_travel_hierarchy(self._journals.keys(), copy=True):
                flattened.append(j)

                if j.notified_dependents:
                    continue

                j.notify_dependents()

                if self._restart_commit_notify:
                    break
            if self._restart_commit_notify:
                continue

            self._call_parent_hook("notify")
            if not self._restart_commit_notify:
                break

        assert not self._restart_commit_notify, "Restart flag should be false after notify loop."
        if __debug__:
            for j in self._journals.values():
                if not j.notified_dependents:
                    self.log.error(t"Journal {j.instance_name} did not notify dependents.")
        assert all(j.notified_dependents for j in self._journals.values()), "All journals should have notified dependents after notify loop."

        # Freeze all journals to prevent further edits
        for j in self._journals.values():
            j.freeze()

        # Done
        self._after_commit_notify = True
        return flattened

    # MARK: Commit - Apply
    def _commit_apply(self, flattened: Sequence[Journal]) -> None:
        """Iterate through flattened hierarchy, flatten updates and apply them (creating new entity versions, or deleting them as requested)."""
        self.log.debug("Committing journals...")

        # Apply all journals in dependency order
        for j in flattened:  # for j in self._commit_travel_hierarchy(self._journals.keys(), copy=False):
            j.commit()
            assert j.superseded, "Journal should be marked as superseded after commit."

        # Check for newly-created unreachable entities and revert them
        for uid in self._created:
            entity = Entity.by_uid(uid)
            if not entity.is_reachable(recursive=True, use_journal=True):
                self.log.warning(t"Entity {entity.instance_name} created in this session is unreachable; reverting. This may indicate a logic bug.")
                entity.revert()

        self._call_parent_hook("apply")
