# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Any, overload, TYPE_CHECKING, Callable, override, cast as typing_cast
from collections.abc import Sequence

if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison
    from ....journal.entity_journal import EntityJournal

from ...ordered_view.sort_key_protocol import SortKeyProtocol
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
        self._update_frontier_sort_key(self.item_sort_key(value))
        self.clear_sort_cache()

    def item_sort_key(self, item : SortKeyProtocol) -> SupportsRichComparison:
        return self._get_container().item_sort_key(item)

    def _update_frontier_sort_key(self, sort_key : SupportsRichComparison) -> None:
        # Store the lowest sort key that has been modified - this is the "frontier" sort key and will be used as part of the invalidation flow
        container = self._get_container()
        frontier_cmp_fn = max if container.item_sort_reverse else min
        self._frontier_sort_key = sort_key if self._frontier_sort_key is None else frontier_cmp_fn(self._frontier_sort_key, sort_key)

    @property
    def sorted(self) -> Sequence[T]:
        return self._get_container().sorted

    def clear_sort_cache(self) -> None:
        # The original container is immutable and thus will never have its sort cache cleared
        # However, if this set has been edited, then the mutable container may have a sort cache that needs to be cleared
        if self.edited:
            self._get_mut_container().clear_sort_cache()

    def on_item_journal_invalidated(self, entity_journal : EntityJournal) -> None:
        original_sort_key = self.item_sort_key(entity_journal.entity)
        new_sort_key = self.item_sort_key(entity_journal)
        if original_sort_key != new_sort_key:
            # We assume that T is Uid here. If it isn't then we shouldn't be here anyway, but this only affects the audit log, so it's not critical even if we are
            self._append_journal(JournalledSetEditType.ITEM_UPDATED, typing_cast(T, entity_journal.entity.uid))
            self._update_frontier_sort_key(new_sort_key)


    @property
    def frontier_sort_key(self) -> SupportsRichComparison | None:
        return self._frontier_sort_key

    @overload
    def __getitem__(self, index: int) -> T: ...
    @overload
    def __getitem__(self, index: slice) -> Sequence[T]: ...
    def __getitem__(self, index: int | slice) -> T | Sequence[T]:
        return self.sorted[index]