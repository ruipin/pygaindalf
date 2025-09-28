# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""
Unit tests for the @classproperty decorator in pygaindalf.
Tests class-level and instance-level access, and dynamic changes.
"""

from abc import ABCMeta, abstractmethod
import pytest
from app.util.helpers.classproperty import classproperty, cached_classproperty

class MyClass:
    _value = 42

    @classproperty
    def value(cls):
        return cls._value

    @classproperty
    def double_value(cls):
        return cls._value * 2

    @classproperty
    def constant(cls) -> int:
        return 100


class MyAbstractClass(metaclass=ABCMeta):
    @classproperty
    @abstractmethod
    def abstract_property(cls):
        raise NotImplementedError("This is an abstract property.")

class MyConcreteClass(MyAbstractClass):
    @classproperty
    def abstract_property(cls):
        return "Implemented abstract property"


@pytest.mark.helpers
@pytest.mark.classproperty
class TestClassProperty:
    def test_on_class(self):
        assert MyClass.value == 42
        assert MyClass.double_value == 84
        assert MyClass.constant == 100

    def test_on_instance(self):
        obj = MyClass()
        assert obj.value == 42
        assert obj.double_value == 84
        assert obj.constant == 100

    def test_dynamic_change(self):
        MyClass._value = 100
        assert MyClass.value == 100
        assert MyClass.double_value == 200
        assert MyClass.constant == 100

    def test_abstract_class_property(self):
        with pytest.raises(NotImplementedError):
            MyAbstractClass.abstract_property
        assert MyConcreteClass.abstract_property == "Implemented abstract property"
        concrete_instance = MyConcreteClass()
        assert concrete_instance.abstract_property == "Implemented abstract property"

    def test_cached_classproperty_caches_result(self):
        class CachedExample:
            call_count = 0

            @cached_classproperty
            def expensive(cls):
                cls.call_count += 1
                return {"call_count": cls.call_count}

        first = CachedExample.expensive
        second = CachedExample.expensive
        instance = CachedExample()
        third = instance.expensive

        assert CachedExample.call_count == 1
        assert first is second
        assert first is third
