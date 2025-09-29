# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import ABCMeta
from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, dataclass_transform

from pydantic import Field

from ...util.uid import Uid


@dataclass_transform(kw_only_default=True, field_specifiers=(Field,))
class EntityFieldsBase:
    pass


# MARK: Fields
class EntityFields[T_Uid_Set: AbstractSet[Uid]](EntityFieldsBase, metaclass=ABCMeta):
    # MARK: Basic Attributes
    uid: Uid = Field(
        default_factory=lambda: None,
        validate_default=True,
        json_schema_extra={"readOnly": True},
        description="Unique identifier for the entity.",
    )

    @property
    def instance_name(self) -> str: ...

    # MARK: Uid Sets
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
