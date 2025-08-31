# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest

from app.util.helpers.wrappers import (
    wrapper,
    before,
    before_attribute_check,
)


# MARK: Tests for generic wrapper decorator
@pytest.mark.helpers
@pytest.mark.wrappers
class TestWrapperDecorator:
    def test_basic_wrapper_execution_and_return_value(self):
        calls: list[tuple[str, object]] = []

        @staticmethod
        def my_wrapper(original, self, *args, **kwargs) -> int:
            calls.append(("before", args or kwargs))
            result = original(self, *args, **kwargs)
            calls.append(("after", result))
            # mutate result to prove wrapper return path used
            return result + 1

        class C:
            @wrapper(my_wrapper)
            def times_two(self, x: int) -> int:
                return x * 2

        c = C()
        out = c.times_two(3)
        assert out == 7  # (3*2) + 1 from wrapper
        assert calls == [
            ("before", (3,)),
            ("after", 6),
        ]

    def test_wrapper_passes_kwargs(self):
        trace: list[str] = []

        def wrap(original, self, *args, **kwargs):  # noqa: ANN001
            trace.append(f"wrap:{kwargs['b']}")
            return original(self, *args, **kwargs) * 10

        class C:
            @wrapper(wrap)
            def add(self, a: int, b: int = 0) -> int:
                return a + b

        c = C()
        assert c.add(2, b=5) == 70  # (2+5)=7 *10 in wrapper
        assert trace == ["wrap:5"]


# MARK: Tests for before decorator
@pytest.mark.helpers
@pytest.mark.wrappers
class TestBeforeDecorator:
    def test_before_runs_prior_to_method_body(self):
        order: list[str] = []

        def before_fn(original, self, *args, **kwargs):  # noqa: ANN001
            assert not self.toggled
            order.append("before")

        class C:
            def __init__(self):
                self.toggled = False

            @before(before_fn)
            def act(self) -> int:
                self.toggled = True
                order.append("body")
                return 42

        c = C()
        result = c.act()
        assert result == 42
        assert c.toggled is True
        assert order == ["before", "body"]


# MARK: Tests for attribute check decorator
@pytest.mark.helpers
@pytest.mark.wrappers
class TestBeforeAttributeCheckDecorator:
    def test_attribute_check_passes_and_fails(self):
        class C:
            def __init__(self):
                self.state = "ready"

            @before_attribute_check(attribute="state", desired="ready")
            def go(self) -> str:
                return "ok"

            @before_attribute_check(attribute="state", desired="ready", message="State not ready")
            def go_custom(self) -> str:
                return "ok"

        c = C()
        # Pass case
        assert c.go() == "ok"

        # Fail default message
        c.state = "blocked"
        with pytest.raises(ValueError) as ei:
            c.go()
        msg = str(ei.value)
        assert "Attribute 'state' must be ready" in msg
        assert "go" in msg  # method name context

        # Fail custom message
        with pytest.raises(ValueError) as ei2:
            c.go_custom()
        assert str(ei2.value).startswith("State not ready")

