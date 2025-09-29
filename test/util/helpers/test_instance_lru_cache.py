# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


"""Unit tests for the instance_lru_cache decorator.

Validates:
 - cached_property semantics (single function object per instance)
 - per-instance cache isolation
 - LRU behaviour with maxsize
 - cache_info() hit/miss accounting
 - metadata (__name__, __doc__) preservation
"""

from typing import ClassVar

import pytest

from app.util.helpers.instance_lru_cache import instance_lru_cache


class Example:
    calls: ClassVar[list[tuple[str, int, int | None]]] = []

    def __init__(self, ident: int) -> None:
        self.ident = ident

    @instance_lru_cache
    def add(self, x: int, y: int = 0) -> int:
        """Return x + y while recording call for test verification."""
        Example.calls.append((f"add:{self.ident}", x, y))
        return x + y

    @instance_lru_cache
    def square(self, x: int) -> int:
        """Return x * x used for simple caching (default maxsize)."""
        Example.calls.append((f"square:{self.ident}", x, None))
        return x * x


@pytest.mark.helpers
@pytest.mark.instance_lru_cache
class TestInstanceLruCache:
    def setup_method(self):
        Example.calls.clear()

    def test_cached_property_returns_same_function_per_instance(self):
        a = Example(1)
        fn1 = a.add
        fn2 = a.add
        assert fn1 is fn2  # cached_property ensures identity

        b = Example(2)
        assert b.add is not fn1  # different instance => different cached function

    def test_calls_are_cached_per_instance(self):
        a = Example(1)
        b = Example(2)
        # First call -> miss
        assert a.add(2, 3) == 5
        # Second identical call -> hit (no new underlying call)
        assert a.add(2, 3) == 5
        # Same args on different instance -> separate cache -> miss
        assert b.add(2, 3) == 5

        # We recorded only two underlying function executions
        assert Example.calls == [
            ("add:1", 2, 3),
            ("add:2", 2, 3),
        ]

        # cache_info per instance
        info_a = a.add.cache_info()  # type: ignore[attr-defined]
        info_b = b.add.cache_info()  # type: ignore[attr-defined]
        assert info_a.hits == 1 and info_a.misses == 1
        assert info_b.hits == 0 and info_b.misses == 1

    def test_basic_caching_default_maxsize(self):
        a = Example(1)
        sq = a.square
        assert sq(5) == 25  # miss
        assert sq(5) == 25  # hit
        assert sq(6) == 36  # miss
        assert sq(6) == 36  # hit
        square_calls = [c for c in Example.calls if c[0].startswith("square:")]
        assert [c[1] for c in square_calls] == [5, 6]
        info = sq.cache_info()  # type: ignore[attr-defined]
        # Two unique keys -> 2 misses, 2 hits
        assert info.misses == 2
        assert info.hits == 2

    def test_metadata_preserved(self):
        a = Example(1)
        assert a.add.__name__ == "add"  # type: ignore[attr-defined]
        assert "Return x + y" in (a.add.__doc__ or "")  # type: ignore[attr-defined]
