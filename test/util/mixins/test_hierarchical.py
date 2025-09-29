# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""Unit tests for HierarchicalMixin and related mixins in pygaindalf.

Tests hierarchy and naming behaviors for custom mixin classes.
"""

import pytest

# Classes under test
from app.util.mixins import HierarchicalMixin, NamedMixin


class Hier(HierarchicalMixin):
    ALLOW_CHANGING_INSTANCE_PARENT = True


class HierNamed(HierarchicalMixin, NamedMixin):
    ALLOW_CHANGING_INSTANCE_PARENT = True


@pytest.mark.mixins
@pytest.mark.hierarchical_mixin
class TestHierarchicalMixins:
    def test_fails_wrong_mro_order(self):
        # Creating NamedHier should fail due to incorrect MRO
        with pytest.raises(TypeError):

            class NamedHier(NamedMixin, HierarchicalMixin):
                pass

    def test_construct_no_name(self):
        # Construct a root Hier instance
        a = Hier()
        assert a.instance_parent is None
        assert str(a) == "<Hier>"
        assert a.instance_hierarchy == "Hier"

        # Construct a child Hier instance
        b = Hier(instance_parent=a)
        assert b.instance_parent is a
        assert b.instance_hierarchy == "Hier.Hier"

        # Construct another child
        c = Hier(instance_parent=b)
        assert c.instance_parent is b
        assert c.instance_hierarchy == "Hier.Hier.Hier"

        # Changing parent to a non-hierarchichal object should fail
        with pytest.raises(TypeError):
            b.instance_parent = 5  # pyright: ignore as we know this will fail type checking

        # Change c's parent to a
        Hier.ALLOW_CHANGING_INSTANCE_PARENT = False
        with pytest.raises(RuntimeError):
            c.instance_parent = a
        Hier.ALLOW_CHANGING_INSTANCE_PARENT = True
        c.instance_parent = a
        assert c.instance_parent is a
        assert c.instance_hierarchy == "Hier.Hier"

    def test_construct_with_name(self):
        # Construct a root HierNamed instance with a name
        a = HierNamed(instance_name="name1")
        assert a.instance_parent is None
        assert str(a) == "<HN name1>"
        assert a.instance_hierarchy == "name1"

        # Construct a child Hier instance
        b = Hier(instance_parent=a)
        assert b.instance_parent is a
        assert b.instance_hierarchy == "name1.Hier"

        # Construct another child with a name
        c = HierNamed(instance_parent=b, instance_name="name3")
        assert c.instance_parent is b
        assert str(c) == "<HN name3>"
        assert c.instance_hierarchy == "name1.Hier.name3"

        # Changing parent to a non-hierarchic object should fail
        with pytest.raises(TypeError):
            b.instance_parent = 5  # pyright: ignore as we know this will fail type checking

        # Change c's parent to a
        HierNamed.ALLOW_CHANGING_INSTANCE_PARENT = False
        with pytest.raises(RuntimeError):
            c.instance_parent = b
        HierNamed.ALLOW_CHANGING_INSTANCE_PARENT = True
        c.instance_parent = a
        assert c.instance_parent is a
        assert c.instance_hierarchy == "name1.name3"
