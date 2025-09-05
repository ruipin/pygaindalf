# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override, Iterable, Hashable, get_origin as typing_get_origin, Self
from pydantic_core import core_schema, CoreSchema
from collections.abc import Set, MutableSet

from .frozen_set import OrderedViewFrozenSet


class OrderedViewSet[T : Hashable](OrderedViewFrozenSet[T], MutableSet[T]):
    @classmethod
    def get_immutable_type(cls, source : type[Self] | None = None) -> type[Set[T]]:
        from .frozen_set import OrderedViewFrozenSet
        return OrderedViewFrozenSet[cls.get_concrete_content_type(source)]


    @override
    def _initialize_container(self, data: Iterable[T] | None = None) -> None:
        if getattr(self, '_set', None) is not None:
            raise ValueError("Container is already initialized.")
        self._set = set() if data is None else set(data)

    @override
    def add(self, value : T) -> None:
        if isinstance(self._set, frozenset):
            raise TypeError(f"Cannot modify frozen {self.__class__.__name__}.")
        self._set.add(value)
        self.clear_sort_cache()

    @override
    def discard(self, value : T) -> None:
        if isinstance(self._set, frozenset):
            raise TypeError(f"Cannot modify frozen {self.__class__.__name__}.")
        self._set.discard(value)
        self.clear_sort_cache()

    @override
    def clear(self) -> None:
        if isinstance(self._set, frozenset):
            raise TypeError(f"Cannot modify frozen {self.__class__.__name__}.")
        self._set.clear()
        self.clear_sort_cache()


    # MARK: Pydantic
    @classmethod
    @override
    def get_core_schema(cls, source, handler) -> CoreSchema:
        return core_schema.set_schema(
            core_schema.is_instance_schema(
                cls.get_concrete_content_type(source)
            )
        )


    # MARK: JournalledOrderedViewSet
    @classmethod
    @override
    def __subclasshook__(cls, subclass):
        spr = super().__subclasshook__(subclass)
        if spr is not NotImplemented and spr:
            return True

        mro = subclass.__mro__
        for klass in mro:
            origin = typing_get_origin(klass) or klass
            if origin is cls:
                return True

        from ..journalled.set.ordered_view_set import JournalledOrderedViewSet
        if issubclass(subclass, JournalledOrderedViewSet):
            return True

        return False