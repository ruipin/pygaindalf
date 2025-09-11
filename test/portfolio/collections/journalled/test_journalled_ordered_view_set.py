# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest

from app.portfolio.collections.ordered_view import OrderedViewSet, OrderedViewFrozenSet
from app.portfolio.collections.journalled.set import JournalledOrderedViewSet


class _MutableInts(OrderedViewSet[int]):
    pass


class _FrozenInts(OrderedViewFrozenSet[int]):
    pass


class _JournalledInts(JournalledOrderedViewSet[int, _MutableInts, _FrozenInts]):
    pass


@pytest.mark.portfolio_collections
@pytest.mark.journalled_collections
@pytest.mark.ordered_view_collections
class TestJournalledOrderedViewSet:
    def test_frontier_sort_key_updates_and_cache_invalidation(self):
        original = _FrozenInts({1, 3, 5})
        j = _JournalledInts(original)

        # Initially no edits -> no frontier sort key
        assert j.frontier_sort_key is None

        # Build original cache first; this should not be affected by later edits
        _ = original.sorted
        orig_info1 = original.sort.cache_info()
        assert orig_info1.misses == 1 and orig_info1.hits == 0

        # First edit: add 4 -> triggers copy-on-write and sets frontier to 4
        j.add(4)
        assert j.edited is True
        assert len(j.journal) == 1
        assert j.journal[0].type.name.lower() in {"add", "discard"}
        assert j.frontier_sort_key == 4

        # Accessing sorted reflects the change and should be consistent across calls
        assert list(j.sorted) == [1, 3, 4, 5]
        assert list(j.sorted) == [1, 3, 4, 5]
        # Original cache remains untouched
        assert original.sort.cache_info().misses == 1

        # Second edit: add 2 -> frontier becomes min(4, 2) = 2
        j.add(2)
        assert len(j.journal) == 2
        assert j.frontier_sort_key == 2
        # Sorted output reflects the new element
        assert list(j.sorted) == [1, 2, 3, 4, 5]
        assert list(j.sorted) == [1, 2, 3, 4, 5]

        # Third edit: discard 3 -> frontier stays at 2
        j.discard(3)
        assert len(j.journal) == 3
        assert j.frontier_sort_key == 2
        # Final state reflects removal and remains consistent across calls
        assert list(j.sorted) == [1, 2, 4, 5]
        assert list(j.sorted) == [1, 2, 4, 5]

    def test_noop_edits_do_not_set_frontier_or_copy(self):
        original = _FrozenInts({1, 2})
        j = _JournalledInts(original)

        # Build original cache and then perform no-op edits
        _ = original.sorted
        assert original.sort.cache_info().misses == 1

        # Add duplicate -> no copy, no frontier update
        j.add(2)
        assert j.edited is False
        assert j.journal == ()
        assert j.frontier_sort_key is None
        assert original.sort.cache_info().misses == 1

        # Discard missing -> still no copy, no frontier update
        j.discard(99)
        assert j.edited is False
        assert j.journal == ()
        assert j.frontier_sort_key is None
        assert original.sort.cache_info().misses == 1
