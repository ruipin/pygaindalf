# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import ABCMeta
from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, dataclass_transform

from pydantic import Field, PositiveInt

from ...util.uid import Uid
from .entity_schema_base import EntitySchemaBase


# MARK: Fields
class EntitySchema[T_Uid_Set: AbstractSet[Uid]](EntitySchemaBase, metaclass=ABCMeta):
    # TODO: These should all be marked Final, but pydantic is broken here, see https://github.com/pydantic/pydantic/issues/10474#issuecomment-2478666651

    # MARK: Basic Attributes
    uid: Uid = Field(
        default_factory=(lambda: None) if TYPE_CHECKING else None,
        validate_default=True,
        json_schema_extra={"readOnly": True},
        description="Unique identifier for the entity.",
    )

    version: PositiveInt = Field(
        default_factory=lambda: None,
        validate_default=True,
        ge=1,
        json_schema_extra={"readOnly": True},
        description="The version of this entity. Incremented when the entity is cloned as part of an update action.",
    )

    @property
    def instance_name(self) -> str: ...

    # MARK: Uid Sets
    # TODO: Fix annotations and dependencies
    if TYPE_CHECKING:
        annotation_uids: T_Uid_Set = Field(default=...)
        extra_dependency_uids: T_Uid_Set = Field(default=...)
    else:
        annotation_uids: frozenset[Uid] = Field(
            default_factory=frozenset,
            description="The UIDs of annotations associated with this entity.",
        )

        extra_dependency_uids: frozenset[Uid] = Field(
            default_factory=frozenset,
            exclude=True,
            repr=False,
            json_schema_extra={"propagate": False},
            description="Extra dependency UIDs. These can be used to create dependencies in addition to those automatically tracked by the entity.",
        )
