# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf

import pytest
from app.util.helpers.callguard import callguard_class
from app.util.helpers.wrappers import wrapper, before, before_attribute_check


@pytest.mark.helpers
@pytest.mark.callguard_with_wrappers
class TestCallguardWithWrappers:
    def test_wrapper_decorator_invoked_on_internal_call(self):
        events: list[str] = []

        @wrapper
        def custom_wrapper(wrapped, *args, **kwargs):  # type: ignore
            events.append(f"wrapper:{wrapped.__name__}")
            result = wrapped(*args, **kwargs)
            if isinstance(result, str):
                return f"W:{result}"
            return result

        @callguard_class(decorator=custom_wrapper, decorate_private_methods=True, decorate_public_methods=False)
        class Sample:
            def __init__(self) -> None:
                self.invoked: list[str] = []

            def _hidden(self) -> str:
                self.invoked.append("_hidden")
                return "ok"

            def public(self) -> str:
                return self._hidden()

        s = Sample()
        with pytest.raises(RuntimeError):
            s._hidden()
        assert events == []
        assert s.public() == "W:ok"
        assert events == ["wrapper:_hidden"]
        assert s.invoked == ["_hidden"]

    def test_before_wrapper_runs_before_internal_call(self):
        events: list[str] = []

        @before
        def log_before(wrapped, *args, **kwargs):  # type: ignore
            events.append(f"before:{wrapped.__name__}")

        @callguard_class(decorator=log_before, decorate_private_methods=True, decorate_public_methods=False)
        class Sample:
            def _a(self) -> str:
                return "A"

            def call(self) -> str:
                return self._a()

        s = Sample()
        with pytest.raises(RuntimeError):
            s._a()
        assert events == []
        assert s.call() == "A"
        assert events == ["before:_a"]

    def test_before_attribute_check_pass_internal_fail_external(self):
    # Use attribute check decorator as the custom decorator for guarding
        attr_check_decorator = before_attribute_check(attribute='state', desired='ready')
        @callguard_class(decorator=attr_check_decorator, decorate_private_methods=True, decorate_public_methods=False)
        class Sample:
            def __init__(self) -> None:
                self.state = 'ready'

            def _do(self) -> str:
                return 'ok'

            def run(self) -> str:
                return self._do()

        s = Sample()
        # Direct external call blocked by callguard before attribute check executes
        with pytest.raises(RuntimeError):
            s._do()
        # Internal call passes attribute check
        assert s.run() == 'ok'

    def test_before_attribute_check_fails_internal(self):
        attr_check_decorator = before_attribute_check(attribute='state', desired='ready')
        @callguard_class(decorator=attr_check_decorator, decorate_private_methods=True, decorate_public_methods=False)
        class Sample:
            def __init__(self) -> None:
                self.state = 'not_ready'

            def _do(self) -> str:
                return 'ok'

            def run(self) -> str:
                return self._do()

        s = Sample()
        with pytest.raises(RuntimeError):
            s._do()  # still blocked externally (callguard)
        # Internal call triggers attribute check and raises ValueError
        with pytest.raises(ValueError):
            s.run()
