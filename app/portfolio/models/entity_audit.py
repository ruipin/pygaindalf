# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from datetime import datetime
from pydantic import Field, ConfigDict, PrivateAttr, computed_field
from enum import Enum
from collections.abc import MutableSequence
from typing import override

from ...util.mixins.models import LoggableHierarchicalNamedModel

from .uid import Uid


class EntityAuditType(Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


class EntityAudit(LoggableHierarchicalNamedModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
    )

    what    : EntityAuditType = Field(description="The type of action that was performed on the entity.")
    when    : datetime           = Field(default_factory=datetime.now, description="The date and time when this entity log entry was created.")
    # TODO: 'who' should be a required field
    who     : str | None         = Field(description="The actor who performed the action that created this log entry.")
    # TODO: Instead of a string, this should be the audit log event, or a diff of the changes, etc
    why     : str | None         = Field(default=None, description="Why this action was performed, if known.")


class EntityAuditLog(MutableSequence):
    entity_uid : Uid
    _entries : list[EntityAudit] = PrivateAttr(default_factory=list)

    # TODO: This class needs to be immutable except when the entity is being modified
    @override
    def __getitem__(self, index):
        return self._entries[index]

    @override
    def __delitem__(self, index) -> None:
        del self._entries[index]

    @override
    def __setitem__(self, index, value) -> None:
        self._entries[index] = value

    @override
    def __len__(self) -> int:
        return len(self._entries)

    @override
    def insert(self, index: int, value: EntityAudit) -> None:
        self._entries.insert(index, value)