# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from pydantic import ConfigDict, PositiveInt, Field
from datetime import datetime

from ...util.mixins.models import LoggableHierarchicalNamedModel

class EntityMetaData(LoggableHierarchicalNamedModel):
    model_config = ConfigDict(
        extra='allow',
        frozen=True,
    )

    version     : PositiveInt     = Field(default=1, ge=1, description="The version of the entity. Incremented when the entity mutates.")
    created_at  : datetime        = Field(default_factory=datetime.now, description="The date and time when the entity was created.")
    mutated_at  : datetime | None = Field(default=None, description="The date and time when the entity was last mutated. None if it has never been mutated.")