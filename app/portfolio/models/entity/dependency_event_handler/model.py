# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import ConfigDict, Field, InstanceOf

from .....util.models import LoggableModel
from ..entity_record import EntityRecord
from .base import EntityDependencyEventHandlerBase
from .protocols import EntityDependencyEventAttributeMatcher, EntityDependencyEventEntityMatcher, EntityDependencyEventHandler


class EntityDependencyEventHandlerModel[
    T_Owner: EntityRecord,
    T_Record: EntityRecord,
](
    LoggableModel,
    EntityDependencyEventHandlerBase[T_Owner, T_Record],
):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    handler: InstanceOf[EntityDependencyEventHandler[T_Owner, T_Record]] = Field(description="The handler function to be called when the event is triggered.")
    on_updated: bool = Field(description="Whether to trigger the handler on update events.")
    on_deleted: bool = Field(description="Whether to trigger the handler on delete events.")
    entity_matchers: (
        tuple[InstanceOf[EntityDependencyEventEntityMatcher[T_Owner, T_Record]], ...] | InstanceOf[EntityDependencyEventEntityMatcher[T_Owner, T_Record]] | None
    ) = Field(default=None, description="Matchers to filter which entities the handler should respond to.")
    attribute_matchers: (
        tuple[InstanceOf[EntityDependencyEventAttributeMatcher[T_Owner, T_Record]] | str, ...]
        | InstanceOf[EntityDependencyEventAttributeMatcher[T_Owner, T_Record]]
        | str
        | None
    ) = Field(default=None, description="Matchers to filter which attributes the handler should respond to.")


# Force a rebuild to ensure any forward references in the base class are properly resolved
EntityDependencyEventHandlerModel.model_rebuild()
