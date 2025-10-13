# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref

from typing import cast as typing_cast
from typing import override

from pydantic import Field, field_validator

from ..helpers.weakref import WeakRef
from ..mixins import HierarchicalProtocol, NamedProtocol, ParentType
from .hierarchical_root import HierarchicalRootModel


class HierarchicalModel(HierarchicalRootModel):
    instance_parent_weakref: WeakRef[ParentType] | None = Field(
        default=None,
        repr=False,
        exclude=True,
        alias="instance_parent",
        description="Parent of this instance in the hierarchy. Can be None if this is a root instance.",
    )

    @field_validator("instance_parent_weakref", mode="after")
    @classmethod
    def _validate_instance_parent(cls, obj: object | None) -> weakref.ref[ParentType] | None:
        if obj is None:
            return None

        _obj = obj
        if isinstance(obj, weakref.ref):
            _obj = obj()
            if _obj is None:
                return None
        else:
            obj = weakref.ref(obj)

        if not isinstance(_obj, (HierarchicalProtocol | NamedProtocol)):
            msg = f"Expected HierarchicalProtocol | NamedProtocol | None, got {type(obj)}"
            raise TypeError(msg)

        cls._do_validate_instance_parent(_obj)

        return typing_cast("weakref.ref", obj)

    @classmethod
    def _do_validate_instance_parent(cls, parent: ParentType) -> None:
        pass

    @property
    @override
    def instance_parent(self) -> ParentType | None:
        parent = getattr(self, "instance_parent_weakref", None)
        if parent is None:
            return None
        return parent() if isinstance(parent, weakref.ref) else parent

    @instance_parent.setter
    def instance_parent(self, new_parent: ParentType | None) -> None:
        self.instance_parent_weakref = weakref.ref(new_parent) if new_parent is not None else None
