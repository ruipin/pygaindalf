# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override, Iterable, Hashable, Self
from pydantic_core import core_schema, CoreSchema
from collections.abc import Set, MutableSet

from .collection import OrderedViewCollection


class OrderedViewFrozenSet[T : Hashable](OrderedViewCollection[T], Set[T]):
    @classmethod
    def get_mutable_type(cls, source : type[Self] | None = None) -> type[Set[T]]:
        from .set import OrderedViewSet
        return OrderedViewSet[cls.get_concrete_content_type(source)]


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
                cls.get_concrete_content_type(source)
            )
        )