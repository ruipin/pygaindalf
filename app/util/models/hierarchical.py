# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref

from collections.abc import Collection, Mapping, Sequence
from collections.abc import Set as AbstractSet
from typing import Any, ClassVar, Self, override
from typing import cast as typing_cast

from pydantic import Field, field_validator

from ..helpers.weakref import WeakRef
from ..mixins import HierarchicalProtocol, NamedProtocol, ParentType
from .hierarchical_root import HierarchicalRootModel


class HierarchicalModel(HierarchicalRootModel):
    INSTANCE_PARENT_FIELD_NAMES: ClassVar[AbstractSet[str]] = frozenset(
        (
            "instance_parent",
            "instance_parent_weakref",
            "instance_parent_field_name",
            "instance_parent_field_key",
            "instance_parent_field_key_weakref",
        )
    )

    instance_parent_weakref: WeakRef[ParentType] | None = Field(
        default=None,
        repr=False,
        exclude=True,
        alias="instance_parent",
        description="Parent of this instance in the hierarchy. Can be None if this is a root instance.",
    )

    instance_parent_field_name: str | None = Field(
        default=None,
        repr=False,
        exclude=True,
        description="Parent field name in the parent's model that contains this instance. Can be None if not applicable.",
    )

    instance_parent_field_key_weakref: int | str | WeakRef[object] | None = Field(
        default=None,
        repr=False,
        exclude=True,
        description="Index or key of this instance in the parent's collection. Can be None if not applicable.",
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

    @property
    def instance_parent_field_key(self) -> int | str | object | None:
        key = getattr(self, "instance_parent_field_key_weakref", None)
        if key is None:
            return None
        if isinstance(key, weakref.ref):
            return key()
        return key

    @instance_parent_field_key.setter
    def instance_parent_field_key(self, new_key: int | str | object | weakref.ref | None) -> None:
        if new_key is None or isinstance(new_key, (int, str, weakref.ref)):
            self.instance_parent_field_key_weakref = new_key
        else:
            self.instance_parent_field_key_weakref = weakref.ref(new_key)

    def _clear_instance_parent_data(self) -> None:
        object.__setattr__(self, "instance_parent_weakref", None)
        object.__setattr__(self, "instance_parent_field_name", None)
        object.__setattr__(self, "instance_parent_field_key_weakref", None)

    @property
    def instance_parent_field_or_none(self) -> Collection | None:
        parent = self.instance_parent
        if parent is None:
            return None

        field_name = self.instance_parent_field_name
        if field_name is None:
            return None

        field = getattr(parent, field_name, None)
        if field is None:
            return None

        if not isinstance(field, Collection):
            msg = f"Expected parent field '{field_name}' to be a Collection, got {type(field)}"
            raise TypeError(msg)
        return field

    @property
    def instance_parent_field(self) -> Collection:
        if (collection := self.instance_parent_field_or_none) is None:
            msg = "This instance does not have a parent field collection."
            raise AttributeError(msg)
        return collection

    def _get_previous_key(self) -> int | None:
        key = self.instance_parent_field_key
        if key is None or not isinstance(key, int) or key <= 0:
            return None

        assert self._get_instance_parent_collection_element(key) is self, "Current instance not found in parent collection."
        return key - 1

    def _get_instance_parent_collection_element(self, key: Any) -> Any:
        collection = self.instance_parent_field_or_none
        if collection is None:
            return None

        if isinstance(collection, Mapping):
            return collection.get(key, None)
        elif isinstance(collection, Sequence):
            return collection[key]
        else:
            return None

    @property
    def previous(self) -> Self | None:
        key = self._get_previous_key()

        if key is None:
            return None

        previous = self._get_instance_parent_collection_element(key)
        if previous is None:
            msg = "Could not find previous element in parent collection."
            raise AttributeError(msg)

        return previous
