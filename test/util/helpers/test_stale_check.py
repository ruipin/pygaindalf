# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf

import pytest

from app.portfolio.models.entity.superseded import superseded_check
from app.util.callguard import callguard_class, CALLGUARD_ENABLED


@pytest.mark.helpers
@pytest.mark.wrappers
@pytest.mark.superseded_check
class TestSupersededCheckStandalone:
    def test_superseded_check_method_pass_and_fail(self):
        class Sample:
            def __init__(self):
                self._superseded = False

            @property
            def superseded(self) -> bool:  # attribute inspected by decorator
                return self._superseded

            @superseded_check
            def do(self) -> str:
                return "ok"

        s = Sample()
        # Pass (superseded == False)
        assert s.do() == "ok"
        # Force superseded and confirm failure
        s._superseded = True
        with pytest.raises(ValueError) as ei:
            s.do()
        msg = str(ei.value)
        assert "Superseded check failed" in msg
        assert "Sample.do" in msg  # method context included

    def test_superseded_check_on_property_access(self):
        class WithProp:
            def __init__(self):
                self._superseded = False

            @property
            def superseded(self) -> bool:
                return self._superseded

            @property
            @superseded_check
            def value(self) -> int:
                return 42

        w = WithProp()
        assert w.value == 42  # passes when not superseded
        w._superseded = True
        with pytest.raises(ValueError) as ei:
            _ = w.value
        msg = str(ei.value)
        assert "Superseded check failed" in msg
        assert "WithProp.value" in msg


@pytest.mark.helpers
@pytest.mark.wrappers
@pytest.mark.superseded_check
@pytest.mark.callguard
@pytest.mark.skipif(not CALLGUARD_ENABLED, reason="callguard not enabled")
class TestSupersededCheckWithCallguard:
    def test_superseded_check_decorates_public_methods_via_callguard(self):
        @callguard_class(decorator=superseded_check, decorate_public_methods=True, decorate_ignore_patterns='superseded')
        class Guarded:
            def __init__(self):
                self._superseded = False

            @property
            def superseded(self) -> bool:
                return self._superseded

            def action(self) -> str:
                return "done"

        g = Guarded()
        # Initially succeeds
        assert g.action() == "done"
        # Mark superseded and verify failure now that the method is decorated
        g._superseded = True
        with pytest.raises(ValueError) as ei:
            g.action()
        msg = str(ei.value)
        assert "Superseded check failed" in msg
        assert "Guarded.action" in msg
        # Accessing the superseded attribute itself should still work (not decorated)
        assert g.superseded is True
