# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""Unit tests for NamedMixin in pygaindalf.

Tests instance naming and string representation for NamedMixin.
"""

import pytest

# Classes under test
from app.util.mixins import NamedMixin


class Named(NamedMixin):
    pass


@pytest.mark.mixins
@pytest.mark.named_mixin
class TestNamedMixin:
    def test_construct_no_name(self):
        # Construct a Named instance without a name
        a = Named()

        expected = Named.__name__
        assert a.instance_name is None  # Verify the instance name is None
        assert a.final_instance_name == expected  # Verify the instance name defaults to the class name
        assert str(a) == f"<{expected}>"  # Verify the string representation matches the expected format

    def test_construct_with_name(self):
        # Construct a Named instance with a custom name
        a = Named(instance_name="some")

        assert a.instance_name == "some"  # Verify the instance name matches the provided name
        assert str(a) == "<N some>"  # Verify the string representation matches the expected format"
