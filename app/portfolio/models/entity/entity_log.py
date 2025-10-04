# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime

from collections.abc import Collection, Iterator, Sequence
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Self, override
from typing import cast as typing_cast

from frozendict import frozendict
from pydantic import ConfigDict, Field, GetCoreSchemaHandler, PositiveInt, computed_field, model_validator
from pydantic_core import CoreSchema, core_schema

from ....util.callguard import callguard_class
from ....util.helpers.frozendict import FrozenDict
from ....util.mixins import HierarchicalMixinMinimal, LoggableMixin, NamedMixinMinimal
from ....util.models import SingleInitializationModel


if TYPE_CHECKING:
    from ...util.uid import Uid
    from .entity import Entity
    from .entity_record import EntityRecord


# MARK: EntityRecord Modification Type enum
class EntityModificationType(Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"

    @override
    def __str__(self) -> str:
        return self.value

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.name}"


# MARK: EntityRecord Change class
class EntityModification(SingleInitializationModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    what: EntityModificationType = Field(description="The type of modification that was performed on the entity.")
    when: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.UTC), description="The date and time when this entity log entry was created."
    )
    who: str | None = Field(description="The actor who performed the action that created this log entry.")
    why: str | None = Field(default=None, description="Why this action was performed, if known.")
    diff: FrozenDict[str, Any] | None = Field(
        default=None,
        description="A dictionary containing the changes made to the entity, if applicable. This can be used to track what was changed in the entity during this action.",
    )
    version: PositiveInt = Field(ge=1, description="The version of this entity at the time of the audit entry.")

    @model_validator(mode="after")
    def _validate_consistency(self) -> Self:
        if self.version == 1:
            if self.what != EntityModificationType.CREATED:
                msg = "The first audit entry must be of type 'CREATED'."
                raise ValueError(msg)
        return self


# MARK: EntityRecord Audit Log class
@callguard_class()
class EntityLog(Sequence, LoggableMixin, HierarchicalMixinMinimal, NamedMixinMinimal):
    TRACK_ENTITY_DIFF = True

    # MARK: EntityRecord
    _entity_uid: Uid
    _entries: list[EntityModification]

    @classmethod
    def _get_audit_log(cls, uid: Uid) -> Self | None:
        from ..store import EntityStore

        if (store := EntityStore.get_global_store()) is None:
            msg = f"Could not get entity store for {cls.__name__}. The global EntityStore is not set."
            raise ValueError(msg)
        return typing_cast("Self | None", store.get_entity_log(uid))

    def __new__(cls, uid: Uid) -> Self:
        if (instance := cls._get_audit_log(uid)) is None:
            instance = super().__new__(cls)
            instance._post_init(uid)
        return instance

    def __init__(self, uid: Uid) -> None:  # noqa: ARG002
        super().__init__()

    def _post_init(self, uid: Uid) -> None:
        self._entity_uid = uid
        self._entries = []

    @classmethod
    def by_entity(cls, entity: Entity | EntityRecord) -> EntityLog | None:
        return cls._get_audit_log(entity.uid)

    @classmethod
    def by_uid(cls, uid: Uid) -> EntityLog | None:
        return cls._get_audit_log(uid)

    @property
    def entity_uid(self) -> Uid:
        return self._entity_uid

    @property
    def entity_or_none(self) -> Entity | None:
        from .entity import Entity

        return Entity.by_uid_or_none(self.entity_uid)

    @property
    def entity(self) -> Entity:
        from .entity import Entity

        return Entity.by_uid(self.entity_uid)

    @property
    def record_or_none(self) -> EntityRecord | None:
        from .entity_record import EntityRecord

        return EntityRecord.by_uid_or_none(self.entity_uid)

    @property
    def record(self) -> EntityRecord:
        from .entity_record import EntityRecord

        return EntityRecord.by_uid(self.entity_uid)

    # MARK: Instance name/parent
    PROPAGATE_INSTANCE_NAME_FROM_PARENT: ClassVar[bool] = False

    @property
    def instance_name(self) -> str:
        return f"{type(self).__name__}@{self.entity_uid!s}"

    @property
    def instance_parent(self) -> Entity | None:
        """Return the parent entity of this instance, if it exists.

        If the entity does not exist in the entity store, returns None.
        """
        return self.entity_or_none

    # MARK: Pydantic schema
    @classmethod
    def __get_pydantic_core_schema__(cls, source: type[Any], handler: GetCoreSchemaHandler) -> CoreSchema:
        assert source is cls, f"Expected source to be {cls.__name__}, got {source.__name__} instead."
        return core_schema.is_instance_schema(cls)

    # MARK: List-like interface
    @override
    def __getitem__(self, index) -> list[EntityModification]:  # noqa: ANN001 to avoid a complex type hint
        return self._entries[index]

    @override
    def __len__(self) -> int:
        return len(self._entries)

    @override
    def __iter__(self) -> Iterator[EntityModification]:  # pyright: ignore[reportIncompatibleMethodOverride]
        return iter(self._entries)

    # MARK: EntityRecord Diffing
    def _is_diffable_field(self, field_name: str) -> bool:
        return not field_name.startswith("_") and field_name not in ("uid", "version", "instance_parent_weakref")

    def _diff(self, old_record: EntityRecord | None, new_record: EntityRecord | None) -> frozendict[str, Any] | None:
        """Return a dictionary containing the differences between the old and new entities.

        This is used to track changes made to the entity record during an update action.
        """
        if not self.TRACK_ENTITY_DIFF:
            return None

        # Sanity check types
        from .entity_record import EntityRecord

        if old_record is not None and not isinstance(old_record, EntityRecord):
            msg = f"Old record must be an EntityRecord or None, got {type(old_record).__name__} instead."
            raise TypeError(msg)
        if new_record is not None and not isinstance(new_record, EntityRecord):
            msg = f"New record must be an EntityRecord or None, got {type(new_record).__name__} instead."
            raise TypeError(msg)

        # If both entities are None, something went wrong
        if old_record is None and new_record is None:
            msg = "Both old and new entities are None. Cannot compute diff."
            raise ValueError(msg)

        # If there is no old record, then all model fields in the record are new
        if old_record is None and new_record is not None:
            diff = {}
            for fldnm in type(new_record).model_fields:
                if not self._is_diffable_field(fldnm):
                    continue
                v = getattr(new_record, fldnm, None)
                if v is None:
                    continue
                if isinstance(v, Collection) and len(v) == 0:
                    continue
                diff[fldnm] = v
            return frozendict(diff)

        # If there is no new record, then all model fields in the old record are removed
        elif new_record is None and old_record is not None:
            diff = {}
            for fldnm in type(old_record).model_fields:
                if not self._is_diffable_field(fldnm):
                    continue
                v = getattr(old_record, fldnm, None)
                if v is None:
                    continue
                if isinstance(v, Collection) and len(v) == 0:
                    continue
                diff[fldnm] = None
            return frozendict(diff)

        # Otherwise, both entities exist, and we take the journal diff
        else:
            assert new_record is not None, "New record must not be None"
            assert old_record is not None, "Old record must not be None"
            journal = old_record.get_journal(create=False, fail=False)
            return journal.get_diff() if journal is not None else self._diff_manual(old_record, new_record)

    def _diff_manual(self, old_record: EntityRecord, new_record: EntityRecord) -> frozendict[str, Any] | None:
        diff = {}

        keys = set(old_record.__dict__.keys())
        keys.update(set(new_record.__dict__.keys()))

        for key in keys:
            if not self._is_diffable_field(key):
                continue

            old_value = getattr(old_record, key, None)
            new_value = getattr(new_record, key, None)

            from .entity_record import EntityRecord

            mismatch = False
            if not isinstance(new_value, type(old_value)):
                mismatch = True
            elif isinstance(old_value, EntityRecord) or (eq := getattr(old_value, "__eq__", None)) is None or (eq_res := eq(new_value)) is NotImplemented:
                mismatch = old_value is not new_value
            else:
                mismatch = not eq_res

            if mismatch:
                diff[key] = new_value

        return frozendict(diff)

    # MARK: EntityRecord Registration
    def _add_entry(self, entry: EntityModification | None = None, /, **kwargs) -> None:
        if entry is None:
            entry = EntityModification(**kwargs)

        if entry.version != self.next_version:
            msg = f"Entry version {entry.version} does not match the expected next version {self.next_version}. The version should be incremented when the entity is cloned as part of an update action."
            raise ValueError(msg)
        if entry.what == EntityModificationType.DELETED and not self.exists:
            msg = "Cannot add a DELETED entry to an entity that does not exist. The entity must be created first."
            raise ValueError(msg)
        self._entries.append(entry)

    def on_init_record(self, record: EntityRecord) -> None:
        from .entity_record import EntityRecord

        if not isinstance(record, EntityRecord):
            msg = f"Expected an EntityRecord instance, got {type(record).__name__} instead."
            raise TypeError(msg)

        if record.uid != self.entity_uid:
            msg = f"EntityRecord UID {record.uid} does not match the audit log's entity UID {self.entity_uid}."
            raise ValueError(msg)

        if record.version != self.next_version:
            msg = f"EntityRecord version {record.version} does not match the expected version {self.next_version}. The version should be incremented when the entity is cloned as part of an update action."
            raise ValueError(msg)

        what = EntityModificationType.CREATED if not self.exists else EntityModificationType.UPDATED

        session = record.session_or_none

        diff = None
        if (self_record := self.record_or_none) is None or record is not self_record:
            old_record = None if (entity := self.entity_or_none) is None else entity.record_or_none
            diff = self._diff(old_record, record)
            self._reset_log_cache()

        self._add_entry(
            what=what,
            when=datetime.datetime.now(tz=datetime.UTC),
            who=session.actor if session is not None else None,
            why=session.reason if session is not None else None,
            diff=diff,
            version=record.version,
        )

    def on_delete_record(self, record: EntityRecord, who: str | None = None, why: str | None = None) -> None:
        from .entity_record import EntityRecord

        if not isinstance(record, EntityRecord):
            msg = f"Expected an EntityRecord instance, got {type(record).__name__} instead."
            raise TypeError(msg)

        if record.uid != self.entity_uid:
            msg = f"EntityRecord UID {record.uid} does not match the audit log's entity UID {self.entity_uid}."
            raise ValueError(msg)
        if record.version < self.version:
            self.log.warning(
                t"EntityRecord version {record.version} is less than the audit log's version {self.version}. This indicates that the entity has been modified since the last audit entry, which is not allowed."
            )
            return
        if record.version > self.version:
            msg = f"EntityRecord version {record.version} is greater than the audit log's version {self.version} which is not allowed."
            raise ValueError(msg)
        if not self.exists:
            msg = "Cannot delete an entity that does not exist. The entity must be created first."
            raise ValueError(msg)

        if (parent := self.instance_parent) is None or parent.record_or_none is not record:
            self.log.warning(
                t"EntityRecord {record} does not match the audit log's parent entity {parent}. This indicates that the entity has been modified since the last audit entry, which is not allowed."
            )

        old_record = self.record_or_none
        if old_record is None:
            msg = "Cannot delete entity record because the entity record is not available."
            raise ValueError(msg)

        session = record.session_or_none
        diff = self._diff(old_record, None)

        self._reset_log_cache()

        self._add_entry(
            what=EntityModificationType.DELETED,
            when=datetime.datetime.now(tz=datetime.UTC),
            who=who or (session.actor if session is not None else None),
            why=why or (session.reason if session is not None else None),
            diff=diff,
            version=self.next_version,
        )

    # MARK: Properties
    @computed_field(description="The most recent version of the entity")
    @property
    def version(self) -> PositiveInt:
        """Return the version of the entity at the time of the last audit entry.

        If there are no entries, returns 0.
        """
        if not self._entries:
            return 0
        return self._entries[-1].version

    @property
    def next_version(self) -> PositiveInt:
        """Return the next version number that should be used for the entity.

        This is the current version + 1.
        """
        return self.version + 1

    @property
    def most_recent(self) -> EntityModification:
        """Returns the most recent audit entry for the entity, or None if there are no entries."""
        if not self._entries:
            msg = "No audit entries available."
            raise ValueError(msg)
        return self._entries[-1]

    @property
    def exists(self) -> bool:
        if not self._entries:
            return False
        return self.most_recent.what != EntityModificationType.DELETED

    def get_entry_by_version(self, version: PositiveInt) -> EntityModification | None:
        """Return the audit entry for the given version, or None if no such entry exists."""
        if (entry := self._entries[version - 1]) is None:
            return None
        if entry.version != version:
            msg = f"Entry version {entry.version} does not match the requested version {version}."
            raise ValueError(msg)
        return entry

    # MARK: Printing
    @override
    def __str__(self) -> str:
        return f"EntityLog({self.entity_uid}, entries={len(self._entries)})"

    @override
    def __repr__(self) -> str:
        return f"<{self.instance_name} at {hex(id(self))} with {len(self._entries)} entries, exists={self.exists}>"

    def as_tuple(self) -> tuple[EntityModification, ...]:
        """Return the audit log entries as a list.

        This is useful for iterating over the entries.
        """
        return tuple(self._entries)

    def as_json(self) -> list[dict[str, Any]]:
        """Return the audit log entries as a JSON-serializable list of dictionaries.

        This is useful for exporting the audit log to JSON.
        """
        return [entry.model_dump() for entry in self._entries]

    def as_json_str(self, **kwargs) -> str:
        """Return the audit log entries as a JSON string.

        This is useful for exporting the audit log to JSON.
        """
        import json

        return json.dumps(self.as_json(), default=str, **kwargs)
