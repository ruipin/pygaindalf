# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest
from typing import override, Self
from app.util.helpers.callguard import (
    callguard_callable,
    callguard_property,
    Callguard,
    callguard_class,
    no_callguard,
    CallguardWrapped,
    CallguardHandlerInfo,
)

# ---------------------------------------------------------------------------
# MARK: Method sample
# ---------------------------------------------------------------------------
class MethodSample:
    def __init__(self) -> None:
        self.invocations: list[str] = []

    @callguard_callable()
    def _secret(self) -> str:
        self.invocations.append("_secret")
        return "ok"

    def call_secret(self) -> str:  # internal allowed
        return self._secret()


@pytest.mark.helpers
@pytest.mark.callguard
class TestCallguardMethods:
    def test_private_method_direct_call_raises(self):
        obj = MethodSample()
        with pytest.raises(RuntimeError):
            obj._secret()
        assert obj.invocations == []

    def test_private_method_internal_call_allowed(self):
        obj = MethodSample()
        result = obj.call_secret()
        assert result == "ok"
        assert obj.invocations == ["_secret"]


# ---------------------------------------------------------------------------
# MARK: Property sample
# ---------------------------------------------------------------------------
class PropertySample:
    def __init__(self) -> None:
        self._value = 123

    @callguard_property()
    @property
    def _value_prop(self) -> int:
        return self._value

    def read_value_prop(self) -> int:
        return self._value_prop


@pytest.mark.helpers
@pytest.mark.callguard
class TestCallguardProperties:
    def test_private_property_direct_access_raises(self):
        obj = PropertySample()
        with pytest.raises(RuntimeError):
            _ = obj._value_prop

    def test_private_property_internal_access_allowed(self):
        obj = PropertySample()
        assert obj.read_value_prop() == 123


# ---------------------------------------------------------------------------
# MARK: Mixin sample
# ---------------------------------------------------------------------------
class MixinSample(Callguard):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def _hidden(self) -> str:  # guarded by mixin
        self.calls.append("_hidden")
        return "ok"

    def public(self) -> str:
        return self._hidden()


@pytest.mark.helpers
@pytest.mark.callguard
class TestCallguardMixin:
    def test_callguard_mixin_enforces_private(self):
        obj = MixinSample()
        with pytest.raises(RuntimeError):
            obj._hidden()
        assert obj.public() == "ok"
        assert obj.calls == ["_hidden"]


# ---------------------------------------------------------------------------
# MARK: Decorator sample
# ---------------------------------------------------------------------------
@callguard_class()
class DecoratedSample:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def _hidden(self) -> str:  # guarded by decorator
        self.calls.append("_hidden")
        return "ok"

    @no_callguard
    def _disabled(self) -> str:  # explicitly NOT guarded
        return "ok"

    def public(self) -> str:
        return self._hidden()

    @classmethod
    def class_method(cls) -> str:
        return "class ok"

    @classmethod
    def _private_class_method(cls) -> str:
        return "private class ok"

    @staticmethod
    def _private_static_method() -> str:  # static methods not guarded
        return "static ok"


@pytest.mark.helpers
@pytest.mark.callguard
class TestCallguardDecorator:
    def test_callguarded_decorator_enforces_private(self):
        obj = DecoratedSample()
        with pytest.raises(RuntimeError):
            obj._hidden()
        assert obj.public() == "ok"
        assert obj.calls == ["_hidden"]

    def test_callguarded_decorator_no_callguard(self):
        obj = DecoratedSample()
        assert obj._disabled() == "ok"

    def test_callguarded_decorator_class_method(self):
        obj = DecoratedSample()
        with pytest.raises(RuntimeError):
            obj._private_class_method()
        assert obj.class_method() == "class ok"

    def test_static_method_not_guarded(self):
        assert DecoratedSample._private_static_method() == "static ok"


# ---------------------------------------------------------------------------
# MARK: Inheritance sample
# ---------------------------------------------------------------------------
from test.util.helpers.lib.test_callguard_lib import TestDoubleUnderscore


class TestDoubleUnderscoreExtended(TestDoubleUnderscore):
    def access_double_underscore_extended(self) -> str:
        return self._TestDoubleUnderscore__double_underscore() # pyright: ignore [reportAttributeAccessIssue]

    @override
    def normal2(self) -> str:  # override wrapper
        return super().normal2()

    def access_single_underscore_super(self) -> str:
        return super()._single_underscore()

    def _subclass_private(self) -> str:
        return "subclass private ok"

    def subclass_private_access(self) -> str:
        return self._subclass_private()


@pytest.mark.helpers
@pytest.mark.callguard
class TestCallguardInheritance:
    def test_double_underscore_access_within_module(self):
        obj = TestDoubleUnderscoreExtended()
        assert obj.normal() == "normal ok"
        assert obj.normal2() == "normal2 ok"
        assert obj.access_single_underscore_super() == "single underscore ok"
        with pytest.raises(RuntimeError):
            obj._TestDoubleUnderscore__double_underscore() # pyright: ignore [reportAttributeAccessIssue]
        assert obj.access_double_underscore() == "double underscore ok"
        with pytest.raises(RuntimeError):
            obj.access_double_underscore_extended()

    def test_subclass_private_method(self):
        obj = TestDoubleUnderscoreExtended()
        with pytest.raises(RuntimeError):
            obj._subclass_private()
        assert obj.subclass_private_access() == "subclass private ok"


# ---------------------------------------------------------------------------
# MARK: __init_subclass__ sample
# ---------------------------------------------------------------------------
@pytest.mark.helpers
@pytest.mark.callguard
class TestCallguardInitSubclass:
    def test_callguard_preserves_init_subclass(self):
        call_log: list[type] = []

        @callguard_class()
        class BaseWithInitSubclass:
            @classmethod
            def __init_subclass__(cls):
                super().__init_subclass__()
                call_log.append(cls)

            def _hidden(self):
                return "ok"

            def public(self):
                return self._hidden()

        class Derived(BaseWithInitSubclass):
            pass

        assert Derived in call_log
        assert call_log[-1] is Derived

        d = Derived()
        with pytest.raises(RuntimeError):
            d._hidden()
        assert d.public() == "ok"


# ---------------------------------------------------------------------------
# MARK: __callguard_handler__ sample
# ---------------------------------------------------------------------------
@pytest.mark.helpers
@pytest.mark.callguard
class TestCallguardHandler:
    def test_custom_handler_enforces_and_logs(self):
        @callguard_class()
        class HandlerSample:
            logs: list[tuple[str, bool]] = []  # (method_name, is_internal)

            def __callguard_handler__[**P, R](self : Self, method : CallguardWrapped[Self,P,R], info : CallguardHandlerInfo[Self,P,R], *args, **kwargs) -> R:
                # Evaluate default checker once and log
                is_internal = info.default_checker(info)
                HandlerSample.logs.append((info.method_name, is_internal))
                if not is_internal:
                    raise PermissionError("custom unauthorized")
                return method(self, *args, **kwargs)

            def _private(self) -> str:  # guarded
                return "ok"

            def public(self) -> str:
                return self._private()

        obj = HandlerSample()
        # External (direct) call -> handler raises custom error
        with pytest.raises(PermissionError):
            obj._private()
        assert HandlerSample.logs[-1] == ("_private", False)

        # Internal call allowed and logged
        assert obj.public() == "ok"
        assert HandlerSample.logs[-1] == ("_private", True)

    def test_permissive_handler_allows_external_calls(self):
        @callguard_class()
        class PermissiveSample:
            calls: list[str] = []

            def __callguard_handler__[**P, R](self : Self, method : CallguardWrapped[Self,P,R], info : CallguardHandlerInfo[Self,P,R], *args, **kwargs) -> R:
                # Intentionally ignore checker result to allow all calls
                PermissiveSample.calls.append(info.method_name)
                return method(self, *args, **kwargs)

            def _private(self) -> str:  # guarded but handler permits
                return "ok"

        obj = PermissiveSample()
        # Direct external call is allowed because handler does not raise
        assert obj._private() == "ok"
        assert PermissiveSample.calls == ["_private"]

    def test_handler_predicate_distinguishes_internal_vs_external(self):
        @callguard_class()
        class PredicateSample:
            predicate_results: list[bool] = []

            def __callguard_handler__[**P, R](self : Self, method : CallguardWrapped[Self,P,R], info : CallguardHandlerInfo[Self,P,R], *args, **kwargs) -> R:
                # Call checker twice to ensure idempotence (should not change outcome)
                first = info.default_checker(info)
                second = info.default_checker(info)
                assert first == second
                PredicateSample.predicate_results.append(first)
                if not first:
                    raise RuntimeError("blocked")
                return method(self, *args, **kwargs)

            def _private(self) -> str:
                return "ok"

            def caller(self) -> str:
                return self._private()

        obj = PredicateSample()
        # External direct call -> predicate False -> raises
        with pytest.raises(RuntimeError):
            obj._private()
        assert PredicateSample.predicate_results[-1] is False

        # Internal call -> predicate True
        assert obj.caller() == "ok"
        assert PredicateSample.predicate_results[-1] is True

    def test_property_handler_method_name(self):
        @callguard_class()
        class HandlerPropertySample:
            handler_logs: list[tuple[str, bool]] = []

            def __init__(self) -> None:
                self._value = 42

            def __callguard_handler__[**P, R](self : Self, method : CallguardWrapped[Self,P,R], info : CallguardHandlerInfo[Self,P,R], *args, **kwargs) -> R:
                # Record the method name the guard sees
                is_internal = info.default_checker(info)
                HandlerPropertySample.handler_logs.append((info.method_name, is_internal))
                if not is_internal:
                    raise PermissionError("blocked")
                return method(self, *args, **kwargs)

            @property
            def _prop(self) -> int:  # guarded (private name)
                return self._value

            @_prop.setter
            def _prop(self, value: int):  # guarded setter
                self._value = value

            @_prop.deleter
            def _prop(self):  # guarded deleter
                # Use a sentinel value to verify deleter was invoked
                self._value = -1

            def access(self) -> int:
                return self._prop

            def mutate(self, value: int) -> int:
                self._prop = value
                return self._value

            def remove(self) -> int:
                del self._prop
                return self._value

        obj = HandlerPropertySample()
        # External direct property access -> blocked by handler
        with pytest.raises(PermissionError):
            _ = obj._prop
        assert HandlerPropertySample.handler_logs[-1] == ('_prop', False)

        # External direct property set -> blocked by handler
        with pytest.raises(PermissionError):
            obj._prop = 100
        assert HandlerPropertySample.handler_logs[-1] == ('_prop.setter', False)

        # External direct property delete -> blocked by handler
        with pytest.raises(PermissionError):
            del obj._prop
        assert HandlerPropertySample.handler_logs[-1] == ('_prop.deleter', False)

        # Internal access via method -> allowed
        assert obj.access() == 42
        assert HandlerPropertySample.handler_logs[-1] == ('_prop', True)

        # Internal setter via method -> allowed
        assert obj.mutate(99) == 99
        assert HandlerPropertySample.handler_logs[-1] == ('_prop.setter', True)

        # Internal deleter via method -> allowed
        assert obj.remove() == -1
        assert HandlerPropertySample.handler_logs[-1] == ('_prop.deleter', True)

        # Internal access after deleter -> allowed and reflects sentinel value
        assert obj.access() == -1
        assert HandlerPropertySample.handler_logs[-1] == ('_prop', True)


# ---------------------------------------------------------------------------
# MARK: __callguard_filter__ sample
# ---------------------------------------------------------------------------
@pytest.mark.helpers
@pytest.mark.callguard
class TestCallguardFilter:
    def test_callguard_filter_skips_methods(self):
        @callguard_class()
        class FilterSample:
            @classmethod
            def __callguard_filter__(cls, name, value):
                # Only guard names ending with '_guarded'
                return name.endswith('_guarded')

            def _a_guarded(self) -> str:
                return "a"

            def _b_skipped(self) -> str:  # not guarded by filter
                return "b"

            def caller(self) -> tuple[str, str]:
                return self._a_guarded(), self._b_skipped()

        obj = FilterSample()

        # _a_guarded is guarded -> external call blocked
        with pytest.raises(RuntimeError):
            obj._a_guarded()

        # _b_skipped not guarded -> external call allowed
        assert obj._b_skipped() == "b"

        # Internal calls: both accessible (guarded one allowed internally)
        assert obj.caller() == ("a", "b")