# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Any, overload, TYPE_CHECKING, Callable, override
from collections.abc import Sequence

if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison

from ...ordered_view import OrderedViewSet, OrderedViewFrozenSet
from .generic_set import GenericJournalledSet
from .generic_set import JournalledSetEditType


class JournalledOrderedViewSet[T : Any, T_Mutable : OrderedViewSet, T_Immutable : OrderedViewFrozenSet](GenericJournalledSet[T, T_Immutable, T_Mutable, T_Immutable]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._frontier_sort_key : SupportsRichComparison | None = None


    # MARK: OrderedViewSet
    def sort(self, key : Callable[[T], SupportsRichComparison] | None = None, reverse : bool | None = None) -> Sequence[T]:
        return self._get_container().sort(key=key, reverse=reverse)

    @override
    def _append_journal(self, type : JournalledSetEditType, value : T) -> None:
        super()._append_journal(type=type, value=value)

        # Store the lowest sort key that has been modified - this is the "frontier" sort key and will be used as part of the invalidation flow
        frontier_sort_key = self._get_container().item_sort_key(value)
        container = self._get_container()
        frontier_cmp_fn = max if container.item_sort_reverse else min
        self._frontier_sort_key = frontier_sort_key if self._frontier_sort_key is None else frontier_cmp_fn(self._frontier_sort_key, frontier_sort_key)

        # Invalidate the sort cache as the set has been modified
        self.clear_sort_cache()

    @property
    def sorted(self) -> Sequence[T]:
        return self._get_container().sorted

    def clear_sort_cache(self) -> None:
        # The original container is immutable and thus will never have its sort cache cleared
        # However, if this set has been edited, then the mutable container may have a sort cache that needs to be cleared
        if self.edited:
            self._get_mut_container().clear_sort_cache()

    @property
    def frontier_sort_key(self) -> SupportsRichComparison | None:
        return self._frontier_sort_key

    @overload
    def __getitem__(self, index: int) -> T: ...
    @overload
    def __getitem__(self, index: slice) -> Sequence[T]: ...
    def __getitem__(self, index: int | slice) -> T | Sequence[T]:
        return self.sorted[index]