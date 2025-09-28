# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from datetime import datetime
from pydantic import Field, ConfigDict, computed_field, PositiveInt, GetCoreSchemaHandler, model_validator
from pydantic_core import CoreSchema, core_schema
from enum import Enum
from collections.abc import Sequence
from typing import override, ClassVar, Any, TYPE_CHECKING, Self, Iterator
from frozendict import frozendict
from collections.abc import Collection

from ....util.mixins import LoggableMixin, NamedMixinMinimal, HierarchicalMixinMinimal
from ....util.models import SingleInitializationModel
from ....util.callguard import callguard_class
from ....util.helpers.frozendict import FrozenDict

from ...util.uid import Uid

if TYPE_CHECKING:
    from .entity import Entity


# MARK: Entity Audit Type enum
class EntityAuditType(Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"

    @override
    def __str__(self) -> str:
        return self.value

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.name}"


# MARK: Entity Audit class
class EntityAudit(SingleInitializationModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
    )

    what    : EntityAuditType             = Field(description="The type of action that was performed on the entity.")
    when    : datetime                    = Field(default_factory=datetime.now, description="The date and time when this entity log entry was created.")
    who     : str | None                  = Field(description="The actor who performed the action that created this log entry.")
    why     : str | None                  = Field(default=None, description="Why this action was performed, if known.")
    diff    : FrozenDict[str, Any] | None = Field(default=None, description="A dictionary containing the changes made to the entity, if applicable. This can be used to track what was changed in the entity during this action.")
    version : PositiveInt                 = Field(ge=1, description="The version of this entity at the time of the audit entry.")

    @model_validator(mode='after')
    def _validate_consistency(self) -> Self:
        if self.version == 1:
            if self.what != EntityAuditType.CREATED:
                raise ValueError("The first audit entry must be of type 'CREATED'.")
        return self


# MARK: Entity Audit Log class
@callguard_class()
class EntityAuditLog(Sequence, LoggableMixin, HierarchicalMixinMinimal, NamedMixinMinimal):
    TRACK_ENTITY_DIFF = True

    # MARK: Entity
    _entity_uid : Uid
    _entries : list[EntityAudit]

    @classmethod
    def _get_audit_log(cls, uid : Uid):
        from ..store import EntityStore
        if (store := EntityStore.get_global_store()) is None:
            raise ValueError(f"Could not get entity store for {cls.__name__}. The global EntityStore is not set.")
        return store.get_audit_log(uid)

    def __new__(cls, uid : Uid):
        if (instance := cls._get_audit_log(uid)) is None:
            instance = super().__new__(cls)
            instance._post_init(uid)
        return instance

    def __init__(self, uid : Uid):
        super().__init__()

    def _post_init(self, uid : Uid):
        self._entity_uid = uid
        self._entries = []

    @classmethod
    def by_entity(cls, entity: Entity) -> EntityAuditLog | None:
        return cls._get_audit_log(entity.uid)

    @classmethod
    def by_uid(cls, uid: Uid) -> EntityAuditLog | None:
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


    # MARK: Instance name/parent
    PROPAGATE_INSTANCE_NAME_FROM_PARENT : ClassVar[bool] = False

    @property
    def instance_name(self) -> str:
        return f"{type(self).__name__}@{str(self.entity_uid)}"

    @property
    def instance_parent(self) -> Entity | None:
        """
        Returns the parent entity of this instance, if it exists.
        If the entity does not exist in the entity store, returns None.
        """
        return self.entity_or_none


    # MARK: Pydantic schema
    @classmethod
    def __get_pydantic_core_schema__(cls, source: type[Any], handler: GetCoreSchemaHandler) -> CoreSchema:
        assert source is cls
        return core_schema.is_instance_schema(cls)



    # MARK: List-like interface
    @override
    def __getitem__(self, index):
        return self._entries[index]

    @override
    def __len__(self) -> int:
        return len(self._entries)

    @override
    def __iter__(self) -> Iterator[EntityAudit]: # pyright: ignore[reportIncompatibleMethodOverride]
        return iter(self._entries)



    # MARK: Entity Diffing
    def _is_diffable_field(self, field_name: str) -> bool:
        return not field_name.startswith('_') and field_name not in ('uid', 'version', 'entity_log', 'entity_dependents', 'instance_parent_weakref')

    def _diff(self, old_entity: Entity | None, new_entity: Entity | None) -> frozendict[str, Any] | None:
        """
        Returns a dictionary containing the differences between the old and new entities.
        This is used to track changes made to the entity during an update action.
        """
        if not self.TRACK_ENTITY_DIFF:
            return None

        # If both entities are None, something went wrong
        if old_entity is None and new_entity is None:
            raise ValueError("Both old and new entities are None. Cannot compute diff.")

        # If there is no old entity, then all model fields in the entity are new
        elif old_entity is None and new_entity is not None:
            diff = {}
            for fldnm in type(new_entity).model_fields.keys():
                if not self._is_diffable_field(fldnm):
                    continue
                v = getattr(new_entity, fldnm, None)
                if v is None:
                    continue
                if isinstance(v, Collection) and len(v) == 0:
                    continue
                diff[fldnm] = v
            return frozendict(diff)

        # If there is no new entity, then all model fields in the old entity are removed
        elif new_entity is None and old_entity is not None:
            diff = {}
            for fldnm in type(old_entity).model_fields.keys():
                if not self._is_diffable_field(fldnm):
                    continue
                v = getattr(old_entity, fldnm, None)
                if v is None:
                    continue
                if isinstance(v, Collection) and len(v) == 0:
                    continue
                diff[fldnm] = None
            return frozendict(diff)

        # Otherwise, both entities exist, and we take the journal diff
        else:
            assert new_entity is not None and old_entity is not None
            journal = old_entity.get_journal(create=False, fail=False)
            return journal.get_diff() if journal is not None else self._diff_manual(old_entity, new_entity)

    def _diff_manual(self, old_entity: Entity, new_entity: Entity) -> frozendict[str, Any] | None:
        diff = {}

        keys = set(old_entity.__dict__.keys())
        keys.update(set(new_entity.__dict__.keys()))

        for key in keys:
            if not self._is_diffable_field(key):
                continue

            old_value = getattr(old_entity, key, None)
            new_value = getattr(new_entity, key, None)

            from .entity import Entity
            mismatch = False
            if not isinstance(new_value, type(old_value)):
                mismatch = True
            elif isinstance(old_value, Entity) or (eq := getattr(old_value, '__eq__', None)) is None or (eq_res := eq(new_value)) is NotImplemented:
                mismatch = old_value is not new_value
            else:
                mismatch = (not eq_res)

            if mismatch:
                diff[key] = new_value

        return frozendict(diff)



    # MARK: Entity Registration
    def _add_entry(self, entry : EntityAudit | None = None, /, **kwargs) -> None:
        if entry is None:
            entry = EntityAudit(**kwargs)

        if entry.version != self.next_version:
            raise ValueError(f"Entry version {entry.version} does not match the expected next version {self.next_version}. The version should be incremented when the entity is cloned as part of an update action.")
        if entry.what == EntityAuditType.DELETED and not self.exists:
            raise ValueError("Cannot add a DELETED entry to an entity that does not exist. The entity must be created first.")
        self._entries.append(entry)

    def on_init(self, entity: Entity) -> None:
        if entity.uid != self.entity_uid:
            raise ValueError(f"Entity UID {entity.uid} does not match the audit log's entity UID {self.entity_uid}.")

        if entity.version != self.next_version:
            raise ValueError(f"Entity version {entity.version} does not match the expected version {self.next_version}. The version should be incremented when the entity is cloned as part of an update action.")

        what = EntityAuditType.CREATED if not self.exists else EntityAuditType.UPDATED

        session = entity.session_or_none

        diff = None
        if (self_entity := self.entity_or_none) is None or entity is not self_entity:
            old_entity = self.instance_parent
            diff = self._diff(old_entity, entity)
            self._reset_log_cache()

        self._add_entry(
            what=what,
            when=datetime.now(),
            who=session.actor if session is not None else None,
            why=session.reason if session is not None else None,
            diff=diff,
            version=entity.version,
        )

    def on_delete(self, entity: Entity, who : str | None = None, why : str | None = None) -> None:
        if entity.uid != self.entity_uid:
            raise ValueError(f"Entity UID {entity.uid} does not match the audit log's entity UID {self.entity_uid}.")
        if entity.version < self.version:
            self.log.warning(t"Entity version {entity.version} is less than the audit log's version {self.version}. This indicates that the entity has been modified since the last audit entry, which is not allowed.")
            return
        if entity.version > self.version:
            raise ValueError(f"Entity version {entity.version} is greater than the audit log's version {self.version} which is not allowed.")
        if not self.exists:
            raise ValueError("Cannot delete an entity that does not exist. The entity must be created first.")

        if (parent := self.instance_parent) is None or parent is not entity:
            self.log.warning(t"Entity {entity.uid} does not match the audit log's parent entity {parent}. This indicates that the entity has been modified since the last audit entry, which is not allowed.")

        old_entity = self.instance_parent
        if old_entity is None:
            raise ValueError("Cannot delete entity because the entity is not available.")

        session = entity.session_or_none
        diff = self._diff(old_entity, None)

        self._reset_log_cache()

        self._add_entry(
            what=EntityAuditType.DELETED,
            when=datetime.now(),
            who=who or (session.actor if session is not None else None),
            why=why or (session.reason if session is not None else None),
            diff=diff,
            version=self.next_version,
        )



    # MARK: Properties
    @computed_field(description="The most recent version of the entity")
    @property
    def version(self) -> PositiveInt:
        """
        Returns the version of the entity at the time of the last audit entry.
        If there are no entries, returns 0.
        """
        if not self._entries:
            return 0
        return self._entries[-1].version

    @property
    def next_version(self) -> PositiveInt:
        """
        Returns the next version number that should be used for the entity.
        This is the current version + 1.
        """
        return self.version + 1

    @property
    def most_recent(self) -> EntityAudit:
        """
        Returns the most recent audit entry for the entity, or None if there are no entries.
        """
        if not self._entries:
            raise ValueError("No audit entries available.")
        return self._entries[-1]

    @property
    def exists(self) -> bool:
        if not self._entries:
            return False
        return self.most_recent.what != EntityAuditType.DELETED

    def get_entry_by_version(self, version: PositiveInt) -> EntityAudit | None:
        """
        Returns the audit entry for the given version, or None if no such entry exists.
        """
        if (entry := self._entries[version - 1]) is None:
            return None
        if entry.version != version:
            raise ValueError(f"Entry version {entry.version} does not match the requested version {version}.")
        return entry



    # MARK: Printing
    @override
    def __str__(self) -> str:
        return f"EntityAuditLog(uid={self.entity_uid}, entries={len(self._entries)})"

    @override
    def __repr__(self) -> str:
        return f"<EntityAuditLog {self.instance_name} at {hex(id(self))} with {len(self._entries)} entries, exists={self.exists}>"

    def as_tuple(self) -> tuple[EntityAudit, ...]:
        """
        Returns the audit log entries as a list.
        This is useful for iterating over the entries.
        """
        return tuple(self._entries)

    def as_json(self) -> list[dict[str, Any]]:
        """
        Returns the audit log entries as a JSON-serializable list of dictionaries.
        This is useful for exporting the audit log to JSON.
        """
        return [entry.model_dump() for entry in self._entries]

    def as_json_str(self, **kwargs) -> str:
        """
        Returns the audit log entries as a JSON string.
        This is useful for exporting the audit log to JSON.
        """
        import json
        return json.dumps(self.as_json(), default=str, **kwargs)