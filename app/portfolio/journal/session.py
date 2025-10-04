# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime
import weakref

from collections.abc import Callable, Iterable, MutableMapping, MutableSet
from typing import TYPE_CHECKING, Any, ClassVar, TypedDict, override

from pydantic import ConfigDict, Field, PrivateAttr, computed_field, field_validator

from ...util.callguard import CallguardClassOptions
from ...util.models import LoggableHierarchicalModel
from ..models.entity import EntityModificationType, EntityRecord, EntityRecordBase
from ..util.superseded import SupersededError, superseded_check
from ..util.uid import UID_SEPARATOR, IncrementingUidFactory, Uid
from .journal import Journal


if TYPE_CHECKING:
    from .protocols import SessionManagerHookLiteral


class SessionParams(TypedDict):
    actor: str
    reason: str


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

    def _add_record_journal(self, record: EntityRecord) -> Journal | None:
        if self.ended:
            msg = "Cannot add an entity journal to an ended session."
            raise RuntimeError(msg)

        if self._after_commit_notify:
            self.log.warning("Cannot add an entity journal after notification phase.")
            return None

        journal_cls = record.get_journal_class()
        if not issubclass(journal_cls, Journal):
            msg = f"{type(record).__name__} journal class {journal_cls} is not a subclass of EntityJournal."
            raise TypeError(msg)
        journal = journal_cls(instance_parent=weakref.ref(self), record=record)
        self._journals[record.uid] = journal

        self._restart_commit_notify = True

        return journal

    def get_record_journal(self, record: EntityRecord, *, create: bool = True) -> Journal | None:
        if self.ended:
            msg = "Cannot get an entity journal from an ended session."
            raise SupersededError(msg)

        if record.superseded:
            self.log.warning(t"EntityRecord {record.instance_name} is superseded; cannot create or retrieve journal.")
            return None

        journal = self._journals.get(record.uid, None)
        if journal is not None:
            if journal.record is not record:
                if not journal.record.superseded:
                    msg = "EntityRecord journal already exists for a different version of this entity. Use the latest version instead."
                    raise RuntimeError(msg)
                if create:
                    del self._journals[record.uid]
            else:
                return journal

        if create:
            return self._add_record_journal(record)
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

    def abort(self) -> None:
        if self.ended:
            msg = "Cannot abort an ended session."
            raise RuntimeError(msg)

        # No need to do anything if there are no edits to commit
        if not self.dirty:
            return

        # TODO: Log abort
        self.log.warning("Aborting session...")
        self._in_abort = True

        try:
            # Forcefully delete any entity records created in this session
            if self._created:
                self._clear_journals()
                records: set[EntityRecord] = set()

                for uid in self._created:
                    record = EntityRecord.by_uid_or_none(uid)
                    if record is None or record.superseded:
                        continue
                    records.add(record)
                    if not record.marked_for_deletion:
                        record.delete()

                for record in records:
                    record.apply_deletion()

            self._clear()
            self.log.warning("Session aborted.")
            self._call_parent_hook("abort")
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

    def commit(self) -> None:
        if self.ended:
            msg = "Cannot commit an ended session."
            raise SupersededError(msg)

        # No need to do anything if there are no edits to commit
        if not self.dirty:
            return

        # TODO: Log commit
        self.log.info("Committing session...")

        self._in_commit = True
        try:
            self._commit()
            self._clear()
            self._call_parent_hook("commit")
        finally:
            self._in_commit = False
            self._after_commit_notify = False

        self.log.info("Commit concluded.")

    def _commit(self) -> None:
        self._commit_notify()
        self._commit_apply()

    def _commit_travel_hierarchy(
        self, iterable: Iterable[Uid], *, condition: Callable[[EntityRecordBase], bool] | None = None, copy: bool = False
    ) -> Iterable[EntityRecordBase]:
        if copy:
            iterable = list(iterable)
        for uid in iterable:
            record = EntityRecord.by_uid_or_none(uid)
            if record is None or record.superseded:
                continue
            yield from record.iter_hierarchy(condition=condition, use_journal=True)

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

    def _commit_notify_travel_hierarchy_condition(self, e: EntityRecordBase) -> bool:
        j = self._journals.get(e.uid, None)
        return (not j.notified_dependents) if j is not None else False

    def _commit_notify(self) -> None:
        """Notify all journals of changes in dependency order, allowing them to update their diffs accordingly."""
        self.log.info("Notifying journals of changes...")

        pass_count = 0
        while True:
            pass_count += 1
            self.log.debug(t"Starting notify pass {pass_count}...")

            self._restart_commit_notify = False

            for e in self._commit_travel_hierarchy(self._journals.keys(), condition=self._commit_notify_travel_hierarchy_condition, copy=True):
                j = self._journals[e.uid]
                j.notify_dependents()

                if self._restart_commit_notify:
                    break
            if self._restart_commit_notify:
                continue

            self._call_parent_hook("notify")
            if not self._restart_commit_notify:
                break

        assert not self._restart_commit_notify, "Restart flag should be false after notify loop."
        assert all(j.notified_dependents for j in self._journals.values()), "All journals should have notified dependents after notify loop."

        # Freeze all journals to prevent further edits
        for j in self._journals.values():
            j.freeze()

        self._after_commit_notify = True

    # MARK: Commit - Apply
    def _commit_apply_travel_hierarchy_condition(self, e: EntityRecordBase) -> bool:
        j = self._journals.get(e.uid, None)
        return j is not None and not j.superseded

    def _commit_apply(self) -> None:
        """Iterate through flattened hierarchy, flatten updates and apply them (creating new entity versions, or deleting them as requested)."""
        self.log.info("Committing journals...")

        for e in self._commit_travel_hierarchy(self._journals.keys(), condition=self._commit_apply_travel_hierarchy_condition, copy=False):
            j = self._journals[e.uid]
            j.commit()

        self._call_parent_hook("apply")
