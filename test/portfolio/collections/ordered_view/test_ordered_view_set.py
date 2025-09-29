# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


import pytest

from app.portfolio.collections.ordered_view import OrderedViewMutableSet, OrderedViewSet


class _MutableInts(OrderedViewMutableSet[int]):
    pass


@pytest.mark.portfolio_collections
@pytest.mark.ordered_view_collections
class TestOrderedViewMutableSet:
    def test_add_and_discard_updates_sorted_cache(self):
        s = _MutableInts([3, 1])
        info0 = s.sort.cache_info()  # type: ignore[attr-defined]
        assert info0.misses == 0 and info0.hits == 0
        first_sorted = s.sorted  # cache built -> miss
        info1 = s.sort.cache_info()  # type: ignore[attr-defined]
        assert info1.misses == 1 and info1.hits == 0
        assert list(first_sorted) == [1, 3]
        s.add(2)  # invalidates cache
        info_after_add = s.sort.cache_info()  # type: ignore[attr-defined]
        # After invalidation, LRU cache was cleared and rebuilt lazily on next access -> stats reset
        assert info_after_add.misses == 0 and info_after_add.hits == 0
        assert list(s.sorted) == [1, 2, 3]
        info_after_access = s.sort.cache_info()  # type: ignore[attr-defined]
        assert info_after_access.misses == 1 and info_after_access.hits == 0
        s.discard(3)
        info_after_discard = s.sort.cache_info()  # type: ignore[attr-defined]
        assert info_after_discard.misses == 0 and info_after_discard.hits == 0
        assert list(s.sorted) == [1, 2]

    def test_clear(self):
        s = _MutableInts([1, 4, 2])
        _ = s.sorted  # build cache
        assert s.sort.cache_info().misses == 1  # type: ignore[attr-defined]
        s.clear()  # invalidate
        assert s.sort.cache_info().misses == 0  # type: ignore[attr-defined]
        assert len(s) == 0
        assert list(s.sorted) == []  # miss after reset
        assert s.sort.cache_info().misses == 1  # type: ignore[attr-defined]

    def test_add_duplicate_no_effect(self):
        s = _MutableInts([1, 2])
        _ = s.sorted
        hits_before = s.sort.cache_info().hits  # type: ignore[attr-defined]
        s.add(2)  # duplicate: should not change underlying container but still invalidates (conservative) or not - ensure consistent order
        assert list(s.sorted) == [1, 2]
        # Accept either invalidation or not; enforce invariants only
        hits_after = s.sort.cache_info().hits  # type: ignore[attr-defined]
        assert hits_after in (hits_before, 0)

    def test_cannot_modify_if_frozen(self):
        # Ensure the immutable helper returns correct type (don't instantiate generic alias directly)
        m = _MutableInts([1])
        # Force internal container to frozen to simulate improper state change attempt
        m._set = frozenset(m._set)  # type: ignore[attr-defined]
        with pytest.raises(TypeError):
            m.add(2)
        with pytest.raises(TypeError):
            m.discard(1)
        with pytest.raises(TypeError):
            m.clear()

    def test_get_immutable_type_round_trip(self):
        assert _MutableInts.get_immutable_type() == OrderedViewSet[int]

    def test_subclasshook_matches(self):
        # _MutableInts obviously subclass; ensure issubclass path remains True
        assert issubclass(_MutableInts, OrderedViewMutableSet)

    def test_iteration_and_getitem_after_mutations(self):
        s = _MutableInts()
        for v in [5, 1, 3]:
            s.add(v)
        assert list(s) == [1, 3, 5]
        assert s[0] == 1 and list(s[1:]) == [3, 5]

    def test_str_and_repr_sorted_output(self):
        s = _MutableInts([3, 2, 5])
        rep = repr(s)
        assert "<_MutableInts:" in rep and "2" in rep and "5" in rep
        # str() uses underlying sorted sequence
        st = str(s)
        assert "2" in st and "5" in st
