# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override, Iterable, Hashable, Self
from pydantic_core import core_schema, CoreSchema
from collections.abc import Set, MutableSet

from ...models.entity import Entity
from ...util.uid import Uid

from .collection import OrderedViewCollection, OrderedViewUidCollection



class OrderedViewSet[T : Hashable](OrderedViewCollection[T], Set[T]):
    @classmethod
    def get_mutable_type(cls, source : type[Self] | None = None) -> type[MutableSet[T]]:
        from .mutable_set import OrderedViewMutableSet
        klass = source or cls
        return OrderedViewMutableSet[klass.get_content_type()]


    @override
    def _initialize_container(self, data: Iterable[T] | None = None) -> None:
        self._set = frozenset() if data is None else frozenset(data)

    @override
    def _get_container(self) -> Set[T]:
        return self._set


    # MARK: Pydantic
    @classmethod
    @override
    def get_core_schema(cls, source, handler) -> CoreSchema:
        return core_schema.set_schema(
            core_schema.is_instance_schema(
                cls.get_content_type(source)
            )
        )



class OrderedViewUidSet[T : Entity](OrderedViewSet[Uid], OrderedViewUidCollection[T]):
    @classmethod
    @override
    def get_mutable_type(cls, source : type[Self] | None = None) -> type[MutableSet[Uid]]: # pyright: ignore[reportIncompatibleMethodOverride]
        from .mutable_set import OrderedViewUidMutableSet
        klass = source or cls
        return OrderedViewUidMutableSet[klass.get_entity_type()]