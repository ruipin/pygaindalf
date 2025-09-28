# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest

from app.portfolio.collections.ordered_view import OrderedViewSet, OrderedViewMutableSet


class _FrozenInts(OrderedViewSet[int]):
    pass


@pytest.mark.portfolio_collections
@pytest.mark.ordered_view_collections
class TestOrderedViewSet:
    def test_basic_construction_and_iteration_sorted(self):
        s = _FrozenInts({3, 1, 2})
        # Underlying container is a frozenset (unordered) but iteration uses sorted view
        assert isinstance(s._set, frozenset)  # type: ignore[attr-defined]
        assert list(iter(s)) == [1, 2, 3]
        # __getitem__ int index
        assert s[0] == 1 and s[-1] == 3
        # __getitem__ slice
        assert list(s[0:2]) == [1, 2]

    def test_cached_sort_invalidated_only_on_reset(self):
        s = _FrozenInts({2, 1})
        # Before any call, cache empty
        info0 = s.sort.cache_info()  # type: ignore[attr-defined]
        assert info0.hits == 0 and info0.misses == 0 and info0.currsize == 0
        # First access -> miss
        _ = s.sorted
        info1 = s.sort.cache_info()  # type: ignore[attr-defined]
        assert info1.misses == 1 and info1.hits == 0 and info1.currsize == 1
        # Second access -> hit
        _ = s.sorted
        info2 = s.sort.cache_info()  # type: ignore[attr-defined]
        assert info2.misses == 1 and info2.hits == 1 and info2.currsize == 1
        # Reset -> stats cleared
        s.clear_sort_cache()
        info3 = s.sort.cache_info()  # type: ignore[attr-defined]
        assert info3.misses == 0 and info3.hits == 0 and info3.currsize == 0
        # Access again -> new miss after reset
        _ = s.sorted
        info4 = s.sort.cache_info()  # type: ignore[attr-defined]
        assert info4.misses == 1 and info4.hits == 0 and info4.currsize == 1

    def test_len_contains_hash_str_repr(self):
        s = _FrozenInts({5, 1, 9})
        assert len(s) == 3
        assert 5 in s and 7 not in s
        # hash based on underlying container iterator object; ensure it stays stable during lifetime
        h1 = hash(s)
        h2 = hash(s)
        assert h1 == h2
        # String / repr expose sorted order
        assert str(s) == str((1, 5, 9)) or str(s) == str([1,5,9])  # allow tuple or list str formatting
        r = repr(s)
        assert r.startswith("<_FrozenInts:") and "1" in r and "9" in r

    def test_pydantic_validation_success_and_type_error(self):
        # Successful coercion
        ok = _FrozenInts.validate_and_coerce([1, 2, 3])
        assert isinstance(ok, _FrozenInts) and set(ok) == {1, 2, 3}
        # Type mismatch
        with pytest.raises(TypeError):
            _FrozenInts.validate_and_coerce([1, "x"])  # type: ignore[list-item]
        with pytest.raises(TypeError):
            _FrozenInts.validate_and_coerce(123)  # not iterable

    def test_get_mutable_type_round_trip(self):
        assert _FrozenInts.get_mutable_type() == OrderedViewMutableSet[int]

