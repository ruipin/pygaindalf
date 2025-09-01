# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref

from datetime import datetime
from pydantic import Field, ConfigDict, PrivateAttr, computed_field, PositiveInt, GetCoreSchemaHandler, BaseModel, model_validator
from pydantic_core import CoreSchema, core_schema
from enum import Enum
from collections.abc import Sequence, MutableMapping
from typing import override, ClassVar, Any, TYPE_CHECKING, Self, Iterator

from ....util.mixins import LoggableMixin, NamedMixinMinimal, HierarchicalMixinMinimal, SingleInitializationModel
from ....util.helpers import script_info
from ....util.helpers.callguard import callguard_class

from ..uid import Uid

if TYPE_CHECKING:
    from .entity import Entity  # Avoid circular import issues by using TYPE_CHECKING


class EntityAuditType(Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"

    @override
    def __str__(self) -> str:
        return self.value

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class EntityAudit(SingleInitializationModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
    )

    what    : EntityAuditType       = Field(description="The type of action that was performed on the entity.")
    when    : datetime              = Field(default_factory=datetime.now, description="The date and time when this entity log entry was created.")
    # TODO: 'who' should be a required field
    who     : str | None            = Field(description="The actor who performed the action that created this log entry.")
    # TODO: Instead of a string, this should be the audit log event, or a diff of the changes, etc
    why     : str | None            = Field(default=None, description="Why this action was performed, if known.")
    diff    : dict[str, Any] | None = Field(default=None, description="A dictionary containing the changes made to the entity, if applicable. This can be used to track what was changed in the entity during this action.")
    version : PositiveInt           = Field(ge=1, description="The version of this entity at the time of the audit entry.")

    @model_validator(mode='after')
    def _validate_consistency(self) -> Self:
        if self.version == 1:
            if self.what != EntityAuditType.CREATED:
                raise ValueError("The first audit entry must be of type 'CREATED'.")
        return self


@callguard_class()
class EntityAuditLog(Sequence, LoggableMixin, HierarchicalMixinMinimal, NamedMixinMinimal):
    TRACK_ENTITY_DIFF = True

    entity_uid : Uid
    _entity : 'weakref.ref[Entity] | None' = PrivateAttr(default=None)
    _entries : list[EntityAudit]


    _INSTANCE_DICT : ClassVar[MutableMapping[Uid, 'EntityAuditLog']] = dict()
    if script_info.is_unit_test():
        @classmethod
        def reset_state(cls) -> None:
            cls._INSTANCE_DICT.clear()

    def __new__(cls, uid : Uid):
        if (instance := cls._INSTANCE_DICT.get(uid, None)) is None:
            cls._INSTANCE_DICT[uid] = instance = super(EntityAuditLog, cls).__new__(cls)
            instance.__dict__['entity_uid'] = uid
        return instance

    def __init__(self, uid : Uid):
        if self.entity_uid != uid:
            raise ValueError(f"EntityAuditLog UID mismatch: {self.entity_uid} != {uid}.")

        if not hasattr(self, '_entries'):
            self._entries = []
            self._entity = None

    @classmethod
    def from_entity(cls, entity: 'Entity') -> 'EntityAuditLog':
        return cls(entity.uid)

    @property
    def entity(self) -> 'Entity | None':
        return (self._entity() if self._entity is not None else None)


    # MARK: Instance name/parent
    PROPAGATE_INSTANCE_NAME_FROM_PARENT : ClassVar[bool] = False

    @property
    def instance_name(self) -> str:
        return f"Audit@{str(self.entity_uid)}"

    @property
    def instance_parent(self) -> 'Entity | None':
        """
        Returns the parent entity of this audit log, if it exists.
        If the entity is not set, returns None.
        """
        entity = self._entity
        return entity() if entity is not None else None


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



    # MARK: Entity Registration
    def _add_entry(self, entry : EntityAudit | None = None, /, **kwargs) -> None:
        if entry is None:
            entry = EntityAudit(**kwargs)

        if entry.version != self.next_version:
            raise ValueError(f"Entry version {entry.version} does not match the expected next version {self.next_version}. The version should be incremented when the entity is cloned as part of an update action.")
        if entry.what == EntityAuditType.DELETED and not self.exists:
            raise ValueError("Cannot add a DELETED entry to an entity that does not exist. The entity must be created first.")
        self._entries.append(entry)

    def _diff(self, old_entity: 'Entity | None', new_entity: 'Entity | None') -> dict[str, Any] | None:
        """
        Returns a dictionary containing the differences between the old and new entities.
        This is used to track changes made to the entity during an update action.
        """
        if not self.TRACK_ENTITY_DIFF:
            return None

        diff = {}

        keys = set(old_entity.__dict__.keys()) if old_entity is not None else set()
        if new_entity is not None:
            keys.update(set(new_entity.__dict__.keys()))

        for key in keys:
            if key.startswith('_'):
                continue
            if key in ('uid', 'version', 'entity_log'):
                continue

            old_value = getattr(old_entity, key, None) if old_entity is not None else None
            new_value = getattr(new_entity, key, None) if new_entity is not None else None

            from .entity import Entity
            mismatch = False
            if not isinstance(new_value, type(old_value)):
                mismatch = True
            elif isinstance(old_value, Entity) and ((diff_mthd := getattr(old_entity, f'_audit_diff_{key}', None)) is not None or (diff_mthd := getattr(old_entity, f'_audit_diff', None)) is not None):
                mismatch = bool(diff_mthd(key, new_value))
            elif isinstance(old_value, Entity) or (eq := getattr(old_value, '__eq__', None)) is None or (eq_res := eq(new_value)) is NotImplemented:
                mismatch = old_value is not new_value
            else:
                mismatch = (not eq_res)

            if mismatch:
                diff[key] = new_value
        return diff

    def on_create(self, entity: 'Entity') -> None:
        if entity.uid != self.entity_uid:
            raise ValueError(f"Entity UID {entity.uid} does not match the audit log's entity UID {self.entity_uid}.")

        if entity.version != self.next_version:
            raise ValueError(f"Entity version {entity.version} does not match the expected version {self.next_version}. The version should be incremented when the entity is cloned as part of an update action.")

        diff = None
        if entity is not self.entity:
            old_entity = self.instance_parent

            diff = self._diff(old_entity, entity)

            self._entity = weakref.ref(entity)
            self._reset_log_cache()

        self._add_entry(
            what=EntityAuditType.CREATED if not self.exists else EntityAuditType.UPDATED,
            when=datetime.now(),
            # TODO: Grab who/why from Journal
            who='TODO',
            why='TODO',
            diff=diff,
            version=entity.version,
        )

    def on_delete(self, entity: 'Entity', who : str | None = None, why : str | None = None) -> None:
        if entity.uid != self.entity_uid:
            raise ValueError(f"Entity UID {entity.uid} does not match the audit log's entity UID {self.entity_uid}.")
        if entity.version < self.version:
            self.log.warning(f"Entity version {entity.version} is less than the audit log's version {self.version}. This indicates that the entity has been modified since the last audit entry, which is not allowed.")
            return
        if entity.version > self.version:
            raise ValueError(f"Entity version {entity.version} is greater than the audit log's version {self.version} which is not allowed.")

        if (parent := self.instance_parent) is None or parent is not entity:
            self.log.warning(f"Entity {entity} does not match the audit log's parent entity {parent}. This indicates that the entity has been modified since the last audit entry, which is not allowed.")

        old_entity = self.instance_parent
        diff = self._diff(old_entity, None)

        self._entity = None
        self._reset_log_cache()

        self._add_entry(
            what=EntityAuditType.DELETED,
            when=datetime.now(),
            # TODO: Grab who/why from Journal
            who=who or 'TODO',
            why=why or 'TODO',
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