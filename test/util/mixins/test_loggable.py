# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""Unit tests for LoggableMixin and related mixins in pygaindalf.

Tests logging and combined mixin behaviors.
"""

import logging

import pytest

# Classes under test
from app.util.mixins import HierarchicalMixin, LoggableHierarchicalNamedMixin, LoggableMixin, LoggableNamedMixin, NamedMixin


class L(LoggableMixin):
    pass


class LN(LoggableNamedMixin):
    pass


class LHN(LoggableHierarchicalNamedMixin):
    pass


@pytest.mark.mixins
@pytest.mark.loggable_mixin
class TestLoggableMixins:
    def test_fails_wrong_mro_order(self):
        # Creating a class with wrong MRO should raise TypeError
        def _break(mixin: type):
            with pytest.raises(TypeError):

                class Cls(mixin, LoggableMixin):
                    pass

        _break(HierarchicalMixin)
        _break(NamedMixin)

    def test_simple(self):
        # Simple LoggableMixin instance
        a = L()
        assert a.log is not None
        assert a.log.parent == logging.root
        assert a.log.name == "L"

        # LoggableNamedMixin instance
        b = LN()
        assert b.log is not None
        assert b.log.parent == logging.root
        assert b.log.name == "LN"

        # LoggableHierarchicalNamedMixin instance with parent
        c = LHN(instance_name="b", instance_parent=b)
        assert c.log is not None
        assert c.log.parent == b.log
        assert c.log.name == "LN.b"

    def test_class(self):
        # Simple LoggableMixin class
        assert L.log is not None
        assert L.log.parent == logging.root
        assert L.log.name == "T(L)"

        # LoggableNamedMixin class
        assert LN.log is not None
        assert LN.log.parent == logging.root
        assert LN.log.name == "T(LN)"

        # LoggableHierarchicalNamedMixin class
        assert LHN.log is not None
        assert LHN.log.parent == logging.root
        assert LHN.log.name == "T(LHN)"
