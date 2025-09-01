# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest
import functools
import pydantic
from typing import override, Self, Callable, Any, cast as typing_cast
from app.util.helpers.callguard import (
    CallguardClassOptions,
    callguard_callable,
    callguard_property,
    Callguard,
    callguard_class,
    no_callguard,
    CallguardWrapped,
    CallguardHandlerInfo,
    CallguardedModelMixin,
    CallguardError
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
        with pytest.raises(CallguardError):
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
        with pytest.raises(CallguardError):
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
        with pytest.raises(CallguardError):
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
        with pytest.raises(CallguardError):
            obj._hidden()
        assert obj.public() == "ok"
        assert obj.calls == ["_hidden"]

    def test_callguarded_decorator_no_callguard(self):
        obj = DecoratedSample()
        assert obj._disabled() == "ok"

    def test_callguarded_decorator_class_method(self):
        obj = DecoratedSample()
        with pytest.raises(CallguardError):
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
        with pytest.raises(CallguardError):
            obj._TestDoubleUnderscore__double_underscore() # pyright: ignore [reportAttributeAccessIssue]
        assert obj.access_double_underscore() == "double underscore ok"
        with pytest.raises(CallguardError):
            obj.access_double_underscore_extended()

    def test_subclass_private_method(self):
        obj = TestDoubleUnderscoreExtended()
        with pytest.raises(CallguardError):
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
        with pytest.raises(CallguardError):
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
                    raise CallguardError("blocked")
                return method(self, *args, **kwargs)

            def _private(self) -> str:
                return "ok"

            def caller(self) -> str:
                return self._private()

        obj = PredicateSample()
        # External direct call -> predicate False -> raises
        with pytest.raises(CallguardError):
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
            def __callguard_filter__(cls, attribute : str, **kwargs):
                # Only guard names ending with '_guarded'
                return attribute.endswith('_guarded')

            def _a_guarded(self) -> str:
                return "a"

            def _b_skipped(self) -> str:  # not guarded by filter
                return "b"

            def caller(self) -> tuple[str, str]:
                return self._a_guarded(), self._b_skipped()

        obj = FilterSample()

        # _a_guarded is guarded -> external call blocked
        with pytest.raises(CallguardError):
            obj._a_guarded()

        # _b_skipped not guarded -> external call allowed
        assert obj._b_skipped() == "b"

        # Internal calls: both accessible (guarded one allowed internally)
        assert obj.caller() == ("a", "b")


# ---------------------------------------------------------------------------
# MARK: decorator basic functionality
# ---------------------------------------------------------------------------
def custom_decorator[**P,R](func: Callable[P,R]) -> Callable[P,R]:
    """Decorator used in tests to verify that callguard applies a custom decorator.

    Behaviour:
    - If return value is str -> prefix with 'wrapped:'
    - If return value is int -> increment by 1
    """
    @functools.wraps(func)
    def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        result = func(*args, **kwargs)
        if isinstance(result, str):
            result = f"wrapped:{result}"
        elif isinstance(result, int):
            result = result + 1
        return typing_cast(R, result)
    return _wrapper

@pytest.mark.helpers
@pytest.mark.callguard
class TestCallguardCustomDecorator:
    def test_custom_decorator_applied_private_method(self):
        # Disable public method decoration so only the private method is decorated once
        @callguard_class(decorator=custom_decorator, decorate_private_methods=True, decorate_public_methods=False)
        class Sample:
            def __init__(self) -> None:
                self.invoked: list[str] = []

            def _secret(self) -> str:
                self.invoked.append("_secret")
                return "ok"

            def public(self) -> str:
                return self._secret()

        s = Sample()
        # External call blocked BEFORE wrapper executes
        with pytest.raises(CallguardError):  # external direct call blocked
            s._secret()
        # Internal call allowed and decorator executed
        assert s.public() == "wrapped:ok"
        assert s.invoked == ["_secret"]

    def test_custom_decorator_applied_private_property(self):
        # Disable public method decoration so only the private property getter is decorated
        @callguard_class(decorator=custom_decorator, decorate_private_methods=True, decorate_public_methods=False)
        class SampleProp:
            def __init__(self) -> None:
                self._value = 10

            @property
            def _val(self) -> int:
                return self._value

            def read(self) -> int:
                return self._val

        sp = SampleProp()
        with pytest.raises(CallguardError):  # blocked external access; decorator not invoked
            _ = sp._val
        # Internal access via method -> decorator increments int by 1
        assert sp.read() == 11

    def test_custom_decorator_applied_public_method(self):
        @callguard_class(decorate_public_methods=True, decorator=custom_decorator)
        class PublicSample:
            def public(self) -> str:
                return "ok"

            def caller(self) -> str:
                return self.public()

        ps = PublicSample()
        # Direct external call -> decorated once
        assert ps.public() == "wrapped:ok"
        # Internal call via another decorated public method -> double wrapped
        assert ps.caller() == "wrapped:wrapped:ok"

    def test_custom_decorator_public_and_private_methods(self):
        @callguard_class(decorator=custom_decorator, decorate_public_methods=True, decorate_private_methods=True)
        class MixedSample:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def public(self) -> str:
                # Call private method; both should be decorated (public + private)
                return f"pub:{self._secret()}"

            def _secret(self) -> str:
                self.calls.append("_secret")
                return "inner"

            def access_private(self) -> str:
                return self._secret()

        ms = MixedSample()
        # External direct call to public -> allowed, decorated
        assert ms.public() == "wrapped:pub:wrapped:inner"
        # External direct call to private -> blocked
        with pytest.raises(CallguardError):
            ms._secret()
        # Internal call to private via helper method -> decorated
        assert ms.access_private() == "wrapped:wrapped:inner"
        assert ms.calls == ["_secret", "_secret"]  # called once via public, once via access_private

    def test_custom_decorator_applied_public_int_method(self):
        @callguard_class(decorator=custom_decorator, decorate_public_methods=True)
        class PublicInt:
            def value(self) -> int:
                return 10

        pi = PublicInt()
        assert pi.value() == 11  # incremented by decorator

# ---------------------------------------------------------------------------
# MARK: allow_same_module
# ---------------------------------------------------------------------------
# External helper functions in SAME module as guarded classes
def _external_call_allow(obj: 'AllowSameModuleSample') -> str:
    return obj._secret()  # should be allowed (same module)

def _external_call_no_allow(obj: 'NoAllowSameModuleSample') -> str:
    return obj._secret()  # should be blocked


@callguard_class(allow_same_module=True)
class AllowSameModuleSample:
    def _secret(self) -> str:
        return "ok"

    def internal(self) -> str:
        return self._secret()


@callguard_class()
class NoAllowSameModuleSample:
    def _secret(self) -> str:
        return "ok"

    def internal(self) -> str:
        return self._secret()


@pytest.mark.helpers
@pytest.mark.callguard
class TestCallguardAllowSameModule:
    def test_allow_same_module_direct_and_indirect(self):
        a = AllowSameModuleSample()
        assert a._secret() == "ok"  # direct external call allowed
        assert _external_call_allow(a) == "ok"  # helper function call allowed
        assert a.internal() == "ok"

    def test_without_allow_same_module_blocks(self):
        n = NoAllowSameModuleSample()
        with pytest.raises(CallguardError):
            n._secret()
        with pytest.raises(CallguardError):
            _external_call_no_allow(n)
        assert n.internal() == "ok"


# ---------------------------------------------------------------------------
# MARK: decorator_factory
# ---------------------------------------------------------------------------
_factory_calls: list[dict[str, Any]] = []


def _decorator_factory(**options: Any):
    """Return the custom_decorator while recording invocation options."""
    _factory_calls.append({k: v for k, v in options.items() if k in ("method_name", "guard")})

    def _decorator[F](func: F) -> F:  # type: ignore[override]
        wrapped = custom_decorator(func)  # type: ignore[arg-type]
        return typing_cast(F, wrapped)

    return _decorator


@callguard_class(decorator_factory=_decorator_factory, decorate_private_methods=True)
class FactorySample:
    def _secret(self) -> str:
        return "ok"

    def public(self) -> str:
        return self._secret()


@pytest.mark.helpers
@pytest.mark.callguard
class TestCallguardDecoratorFactory:
    def test_decorator_factory_applied(self):
        f = FactorySample()
        with pytest.raises(CallguardError):
            f._secret()
        assert f.public() == "wrapped:ok"
        assert len(_factory_calls) == 1
        assert _factory_calls[0]["method_name"] == "_secret"


# ---------------------------------------------------------------------------
# MARK: __callguard_decorator_factory__ attribute
# ---------------------------------------------------------------------------
_attr_factory_calls: list[str] = []


def _attr_factory(**options: Any):
    _attr_factory_calls.append(options.get("method_name", "?"))

    def _decorator[F](func: F) -> F:  # type: ignore[override]
        wrapped = custom_decorator(func)  # type: ignore[arg-type]
        return typing_cast(F, wrapped)

    return _decorator


@callguard_class(decorate_private_methods=True)
class AttrFactorySample:
    __callguard_decorator_factory__ = staticmethod(_attr_factory)

    def _hidden(self) -> str:
        return "ok"

    def access(self) -> str:
        return self._hidden()


@pytest.mark.helpers
@pytest.mark.callguard
class TestCallguardClassDecoratorFactoryAttribute:
    def test_class_level_factory_attribute(self):
        a = AttrFactorySample()
        with pytest.raises(CallguardError):
            a._hidden()
        assert a.access() == "wrapped:ok"
        assert _attr_factory_calls == ["_hidden"]


# ---------------------------------------------------------------------------
# MARK: guard_ignore_patterns
# ---------------------------------------------------------------------------
@callguard_class(guard_private_methods=True, guard_ignore_patterns=[r"_skip_guard$"])
class GuardIgnoreSample:
    def _will_guard(self) -> str:
        return "guarded"

    def _skip_guard(self) -> str:  # pattern -> not guarded
        return "skipped"

    def both(self) -> tuple[str, str]:
        return self._will_guard(), self._skip_guard()


@pytest.mark.helpers
@pytest.mark.callguard
class TestCallguardGuardIgnorePatterns:
    def test_guard_ignore_patterns(self):
        g = GuardIgnoreSample()
        with pytest.raises(CallguardError):
            g._will_guard()
        assert g._skip_guard() == "skipped"  # not guarded
        assert g.both() == ("guarded", "skipped")


# ---------------------------------------------------------------------------
# MARK: decorate_ignore_patterns
# ---------------------------------------------------------------------------
@callguard_class(
    decorator=custom_decorator,
    decorate_private_methods=True,
    decorate_ignore_patterns=[r"_skip_decorate$"]
)
class DecorateIgnoreSample:
    def _decorated(self) -> str:
        return "ok"

    def _skip_decorate(self) -> str:  # pattern excluded from decoration
        return "ok2"

    def call(self) -> tuple[str, str]:
        return self._decorated(), self._skip_decorate()


@pytest.mark.helpers
@pytest.mark.callguard
class TestCallguardDecorateIgnorePatterns:
    def test_decorate_ignore_patterns(self):
        d = DecorateIgnoreSample()
        with pytest.raises(CallguardError):
            d._decorated()
        with pytest.raises(CallguardError):
            d._skip_decorate()
        assert d.call() == ("wrapped:ok", "ok2")


# ---------------------------------------------------------------------------
# MARK: guard_skip_* options
# ---------------------------------------------------------------------------
@pytest.mark.helpers
@pytest.mark.callguard
class TestCallguardGuardSkipOptions:
    def test_guard_skip_classmethods(self):
        @callguard_class(guard_skip_classmethods=True)
        class Sample:
            def _inst(self) -> str:
                return "i"

            @classmethod
            def _cm(cls) -> str:
                return "c"

            def call_inst(self) -> str:
                return self._inst()

            @classmethod
            def call_cm(cls) -> str:
                return cls._cm()

        s = Sample()
        # Instance private still guarded
        with pytest.raises(CallguardError):
            s._inst()
        # Classmethod private NOT guarded due to skip
        assert Sample._cm() == "c"
        # Internal calls succeed
        assert s.call_inst() == "i"
        assert Sample.call_cm() == "c"

    def test_guard_skip_instancemethods(self):
        @callguard_class(guard_skip_instancemethods=True)
        class Sample2:
            def _inst(self) -> str:
                return "i"

            @classmethod
            def _cm(cls) -> str:
                return "c"

            @classmethod
            def call_cm(cls) -> str:
                return cls._cm()

        s2 = Sample2()
        # Instance private NOT guarded due to skip
        assert s2._inst() == "i"
        # Classmethod private still guarded
        with pytest.raises(CallguardError):
            Sample2._cm()
        # Internal classmethod call allowed
        assert Sample2.call_cm() == "c"

    def test_guard_skip_properties(self):
        @callguard_class(guard_skip_properties=True)
        class Sample3:
            def __init__(self) -> None:
                self._v = 5

            @property
            def _val(self) -> int:
                return self._v

            def access(self) -> int:
                return self._val

            def _hidden(self) -> str:
                return "h"

            def call_hidden(self) -> str:
                return self._hidden()

        s3 = Sample3()
        # Property private NOT guarded due to skip
        assert s3._val == 5
        # Private method still guarded
        with pytest.raises(CallguardError):
            s3._hidden()
        assert s3.call_hidden() == "h"


# ---------------------------------------------------------------------------
# MARK: decorate_skip_* options
# ---------------------------------------------------------------------------
@pytest.mark.helpers
@pytest.mark.callguard
class TestCallguardDecorateSkipOptions:
    def test_decorate_skip_classmethods(self):
        @callguard_class(
            decorator=custom_decorator,
            decorate_private_methods=True,
            decorate_skip_classmethods=True,
        )
        class Sample:
            def _inst(self) -> str:
                return "i"

            @classmethod
            def _cm(cls) -> str:
                return "c"

            def call_inst(self) -> str:
                return self._inst()

            @classmethod
            def call_cm(cls) -> str:
                return cls._cm()

        s = Sample()
        # External calls
        with pytest.raises(CallguardError):
            s._inst()
        with pytest.raises(CallguardError):
            Sample._cm()
        # Internal instance private decorated
        assert s.call_inst() == "wrapped:i"
        # Internal classmethod private NOT decorated
        assert Sample.call_cm() == "c"

    def test_decorate_skip_instancemethods(self):
        @callguard_class(
            decorator=custom_decorator,
            decorate_private_methods=True,
            decorate_skip_instancemethods=True,
            decorate_skip_classmethods=False,
        )
        class Sample2:
            def _inst(self) -> str:
                return "i"

            @classmethod
            def _cm(cls) -> str:
                return "c"

            def call_inst(self) -> str:
                return self._inst()

            @classmethod
            def call_cm(cls) -> str:
                return cls._cm()

        s2 = Sample2()
        with pytest.raises(CallguardError):
            Sample2._cm()
        with pytest.raises(CallguardError):
            s2._inst()
        # Instance private NOT decorated due to skip
        assert s2.call_inst() == "i"
        # Classmethod private decorated
        assert Sample2.call_cm() == "wrapped:c"

    def test_decorate_skip_properties(self):
        @callguard_class(
            decorator=custom_decorator,
            decorate_private_methods=True,
            decorate_skip_properties=True,
        )
        class Sample3:
            def __init__(self) -> None:
                self._v = 5

            @property
            def _val(self) -> int:
                return self._v

            def access(self) -> int:
                return self._val

            def _hidden(self) -> str:
                return "h"

            def call_hidden(self) -> str:
                return self._hidden()

        s3 = Sample3()
        with pytest.raises(CallguardError):
            s3._hidden()
        with pytest.raises(CallguardError):
            _ = s3._val
        # Property NOT decorated -> unchanged value
        assert s3.access() == 5
        # Private method decorated internally
        assert s3.call_hidden() == "wrapped:h"



# ---------------------------------------------------------------------------
# MARK: Pydantic model attributes
# ---------------------------------------------------------------------------
class ModelSample(CallguardedModelMixin, pydantic.BaseModel):
    test       : int = pydantic.Field      (default=0)
    _priv      : int = pydantic.PrivateAttr(default=1)
    __dpriv    : int = pydantic.PrivateAttr(default=2)

    def public(self) -> str:
        return "public ok"

class ModelSample2(ModelSample):
    __callguard_class_options__ = CallguardClassOptions['ModelSample2'](
        guard_public_methods=True
    )

    def public2(self) -> str:
        return "public2 ok"

@pytest.mark.helpers
@pytest.mark.callguard
class TestCallguardPydanticAttributes:
    def test_pydantic_attributes_guarded(self):
        t = ModelSample()

        assert t.test == 0
        with pytest.raises(CallguardError, match=r'Unauthorized call to [a-zA-Z._]+\._priv'):
            t._priv
        with pytest.raises(CallguardError, match=r'Unauthorized call to [a-zA-Z._]+\._ModelSample__dpriv'):
            t._ModelSample__dpriv # pyright: ignore[reportAttributeAccessIssue]
        assert t.public() == "public ok"

        t.test = 10
        assert t.test == 10
        with pytest.raises(CallguardError, match=r'Unauthorized call to [a-zA-Z._]+\._priv'):
            t._priv = 11
        with pytest.raises(CallguardError, match=r'Unauthorized call to [a-zA-Z._]+\._ModelSample__dpriv'):
            t._ModelSample__dpriv = 12 # pyright: ignore[reportAttributeAccessIssue]

    def test_pydantic_redefine_options(self):
        t2 = ModelSample2()

        assert t2.test == 0
        with pytest.raises(CallguardError, match=r'Unauthorized call to [a-zA-Z._]+\._priv'):
            t2._priv
        with pytest.raises(CallguardError, match=r'Unauthorized call to [a-zA-Z._]+\._ModelSample__dpriv'):
            t2._ModelSample__dpriv # pyright: ignore[reportAttributeAccessIssue]
        assert t2.public() == "public ok"

        with pytest.raises(CallguardError, match=r'Unauthorized call to [a-zA-Z._]+\.public2'):
            t2.public2()