# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

"""
Unit tests for LoggableMixin and related mixins in pygaindalf.
Tests logging and combined mixin behaviors.
"""

import pytest
import logging

# Classes under test
from app.util.mixins import LoggableMixin, LoggableNamedMixin, LoggableHierarchicalNamedMixin, HierarchicalMixin, NamedMixin


class L(LoggableMixin):
    pass

class LH(LoggableNamedMixin):
    pass

class LHN(LoggableHierarchicalNamedMixin):
    pass


@pytest.mark.mixins
@pytest.mark.loggable_mixin
class TestLoggableMixins:
    def test_fails_wrong_mro_order(self):
        # Creating a class with wrong MRO should raise TypeError
        def _break(mixin):
            class cls(mixin, LoggableMixin):
                pass
            with pytest.raises(TypeError):
                cls()
        _break(HierarchicalMixin)
        _break(NamedMixin)

    def test_simple(self):
        # Simple LoggableMixin instance
        a = L()
        assert a.log is not None
        assert a.log.parent == logging.root
        assert a.log.name == 'L'

        # LoggableNamedMixin instance
        b = LH()
        assert b.log is not None
        assert b.log.parent == logging.root
        assert b.log.name == 'LH'

        # LoggableHierarchicalNamedMixin instance with parent
        c = LHN(instance_name='b', instance_parent=b)
        assert c.log is not None
        assert c.log.parent == b.log
        assert c.log.name == 'LH.b'