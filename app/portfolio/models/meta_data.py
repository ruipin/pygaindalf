# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from pydantic import ConfigDict, PositiveInt, Field, computed_field
from datetime import datetime

from enum import Enum

from ...util.mixins.models import LoggableHierarchicalNamedModel

from .entity_audit import EntityAuditLog


class EntityMetaData(LoggableHierarchicalNamedModel):
    model_config = ConfigDict(
        extra='allow',
        frozen=True,
    )

    version     : PositiveInt     = Field(default=0, ge=0, description="The version of this entity. Incremented when the entity is cloned as part of an update action.")
    superseded  : bool            = Field(default=False, description="Indicates whether this entity instance has been superseded by another instance with an incremented version.")

    #audit_log  : EntityAuditLog = Field(default_factory=EntityAuditLog, description="Log of actions that have been done on this entity, such as creation, updates, or deletions.")

    # TODO: Implement these
    #@computed_field
    #@property
    #def first_version_at(self) -> datetime:
    #    return self.audit_log.first_version_at

    #@computed_field
    #@property
    #def created_at(self) -> datetime:
    #    return self.audit_log.created_at(self)

    #@computed_field
    #@property
    #def superseded_at(self) -> datetime:
    #    return self.audit_log.superseded_at(self) if self.superseded else None