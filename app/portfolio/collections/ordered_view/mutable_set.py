# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Hashable, Iterable, MutableSet
from collections.abc import Set as AbstractSet
from typing import Self, override
from typing import get_origin as typing_get_origin

from pydantic_core import CoreSchema, core_schema

from .frozen_set import OrderedViewSet


class OrderedViewMutableSet[T: Hashable](OrderedViewSet[T], MutableSet[T]):
    @classmethod
    def get_immutable_type(cls, source: type[Self] | None = None) -> type[AbstractSet[T]]:
        from .frozen_set import OrderedViewSet

        klass = source or cls
        return OrderedViewSet[klass.get_content_type()]

    @override
    def _initialize_container(self, data: Iterable[T] | None = None) -> None:
        if getattr(self, "_set", None) is not None:
            msg = "Container is already initialized."
            raise ValueError(msg)
        self._set = set() if data is None else set(data)

    @override
    def add(self, value: T) -> None:
        if isinstance(self._set, frozenset):
            msg = f"Cannot modify frozen {type(self).__name__}."
            raise TypeError(msg)
        self._set.add(value)
        self.clear_sort_cache()

    @override
    def discard(self, value: T) -> None:
        if isinstance(self._set, frozenset):
            msg = f"Cannot modify frozen {type(self).__name__}."
            raise TypeError(msg)
        self._set.discard(value)
        self.clear_sort_cache()

    @override
    def clear(self) -> None:
        if isinstance(self._set, frozenset):
            msg = f"Cannot modify frozen {type(self).__name__}."
            raise TypeError(msg)
        self._set.clear()
        self.clear_sort_cache()

    # MARK: Pydantic
    @classmethod
    @override
    def get_core_schema(cls, source, handler) -> CoreSchema:  # noqa: ANN001
        return core_schema.set_schema(core_schema.is_instance_schema(cls.get_content_type(source)))

    # MARK: JournalledOrderedViewSet
    @classmethod
    @override
    def __subclasshook__(cls, subclass: type) -> bool:
        spr = super().__subclasshook__(subclass)
        if spr is not NotImplemented and spr:
            return True

        mro = subclass.__mro__
        for klass in mro:
            origin = typing_get_origin(klass) or klass
            if origin is cls:
                return True

        from ..journalled.set.ordered_view_set import JournalledOrderedViewSet

        return bool(issubclass(subclass, JournalledOrderedViewSet))
