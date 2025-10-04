# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Hashable, Iterable, MutableSet
from collections.abc import Set as AbstractSet
from typing import Self, override

from pydantic_core import CoreSchema, core_schema

from .collection import OrderedViewCollection


class OrderedViewSet[T: Hashable](OrderedViewCollection[T], AbstractSet[T]):
    @classmethod
    def get_mutable_type(cls, source: type[Self] | None = None) -> type[MutableSet[T]]:
        from .mutable_set import OrderedViewMutableSet

        return OrderedViewMutableSet[cls.get_content_type(source=source)]

    @override
    def _initialize_container(self, data: Iterable[T] | None = None) -> None:
        self._set = frozenset() if data is None else frozenset(data)

    @override
    def _get_container(self) -> AbstractSet[T]:
        return self._set

    # MARK: Pydantic
    @classmethod
    @override
    def get_core_schema(cls, source, handler) -> CoreSchema:  # noqa: ANN001
        return core_schema.set_schema(core_schema.is_instance_schema(cls.get_content_type(source=source)))
