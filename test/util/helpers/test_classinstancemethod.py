# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""
Unit tests for the @classinstancemethod decorator.
Validates instance-level and class-level invocation, argument forwarding,
subclass behavior, and metadata preservation via functools.wraps.
"""

import inspect
import pytest
from app.util.helpers.classinstancemethod import classinstancemethod


class Sample:
    value = 10

    def __init__(self) -> None:
        self.value = 20

    @classinstancemethod
    def get_value(first):
        """Return `value` from either the class or the instance depending on how it's called."""
        return first.value

    @classinstancemethod
    def add(first, x: int, y: int = 0) -> int:
        """Return value + x + y, where value comes from class or instance."""
        return first.value + x + y


class SampleChild(Sample):
    value = 100

    def __init__(self) -> None:
        self.value = 200


@pytest.mark.helpers
@pytest.mark.classinstancemethod
class TestClassInstanceMethod:
    def test_calls_on_instance(self):
        obj = Sample()
        assert obj.get_value() == 20
        assert obj.add(5, y=2) == 27

    def test_calls_on_class(self):
        assert Sample.get_value() == 10
        assert Sample.add(5, y=2) == 17

    def test_subclass_behavior(self):
        # On class, uses subclass's class attribute
        assert SampleChild.get_value() == 100
        # On instance, uses instance attribute
        child = SampleChild()
        assert child.get_value() == 200
        assert child.add(1) == 201

    def test_wraps_preserves_metadata(self):
        # __name__ and __doc__ are preserved via functools.wraps
        assert Sample.get_value.__name__ == "get_value"
        assert "Return `value`" in (Sample.get_value.__doc__ or "")
        # __wrapped__ enables inspect.signature to reflect the original function
        assert hasattr(Sample.add, "__wrapped__")
        sig = inspect.signature(Sample.add)
        # The original function is (first, x: int, y: int = 0)
        params = list(sig.parameters.values())
        assert [p.name for p in params] == ["first", "x", "y"]
        assert params[2].default == 0
