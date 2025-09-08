# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Any, overload, TYPE_CHECKING, Callable
from collections.abc import Sequence

from .generic_set import GenericJournalledSet
from ...ordered_view import OrderedViewSet, OrderedViewFrozenSet

if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison


class JournalledOrderedViewSet[T : Any, T_Mutable : OrderedViewSet, T_Immutable : OrderedViewFrozenSet](GenericJournalledSet[T, T_Immutable, T_Mutable, T_Immutable]):
    # MARK: OrderedViewSet
    def sort(self, key : Callable[[T], SupportsRichComparison] | None = None, reverse : bool | None = None) -> Sequence[T]:
        return self._get_container().sort(key=key, reverse=reverse)

    @property
    def sorted(self) -> Sequence[T]:
        return self._get_container().sorted

    def clear_sort_cache(self) -> None:
        self._get_container().clear_sort_cache()

    @overload
    def __getitem__(self, index: int) -> T: ...
    @overload
    def __getitem__(self, index: slice) -> Sequence[T]: ...
    def __getitem__(self, index: int | slice) -> T | Sequence[T]:
        return self.sorted[index]