# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""Unit tests for the @classinstanceproperty decorator.

Validates class-level and instance-level access and read-only behavior.
"""

import pytest

from app.util.helpers.classinstanceproperty import classinstanceproperty


class Foo:
    base = 5

    def __init__(self) -> None:
        self.base = 10

    @classinstanceproperty
    def value(self):
        # first is instance when accessed from an instance, else class
        return self.base

    @classinstanceproperty
    def doubled(self):
        return self.base * 2


class Bar(Foo):
    base = 100

    def __init__(self) -> None:
        self.base = 200


@pytest.mark.helpers
@pytest.mark.classinstanceproperty
class TestClassInstanceProperty:
    def test_access_on_class(self):
        assert Foo.value == 5
        assert Foo.doubled == 10

    def test_access_on_instance(self):
        f = Foo()
        assert f.value == 10
        assert f.doubled == 20

    def test_subclass_behavior(self):
        # class-level uses subclass class attribute
        assert Bar.value == 100
        # instance-level uses instance attribute
        b = Bar()
        assert b.value == 200
        assert b.doubled == 400

    def test_read_only_on_instance(self):
        f = Foo()
        with pytest.raises(AttributeError):
            f.value = 1  # type: ignore[attr-defined]
        with pytest.raises(AttributeError):
            del f.value
