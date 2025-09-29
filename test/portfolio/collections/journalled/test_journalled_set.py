# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""Tests for JournalledSet copy-on-write and journaling.

Follows the style of existing JournalledSequence and JournalledMapping tests.
"""

import pytest

from app.portfolio.collections.journalled.set import (
    JournalledSet,
    JournalledSetEditType,
)


@pytest.mark.portfolio_collections
@pytest.mark.journalled_collections
class TestJournalledSet:
    def test_no_edit_pass_through(self):
        original = {1, 2, 3}
        js = JournalledSet(original)
        assert js.edited is False
        assert 1 in js  # membership before edits
        assert len(js) == len(original)
        # journal should be empty before any edits
        assert js.journal == ()

    def test_add_triggers_copy_and_journal(self):
        original = {1, 2}
        js = JournalledSet(original)
        js.add(3)
        assert js.edited is True
        assert 3 in js
        assert 3 not in original  # original unchanged
        assert len(js.journal) == 1
        e = js.journal[0]
        assert e.type is JournalledSetEditType.ADD and e.value == 3

    def test_add_duplicate_no_journal(self):
        original = {1, 2}
        js = JournalledSet(original)
        js.add(2)  # already present
        assert js.edited is False  # no copy-on-write
        assert js.journal == ()

    def test_discard_triggers_copy_and_journal(self):
        original = {1, 2, 3}
        js = JournalledSet(original)
        js.discard(2)
        assert js.edited is True
        assert 2 not in js
        assert 2 in original  # original unchanged
        assert len(js.journal) == 1
        e = js.journal[0]
        assert e.type is JournalledSetEditType.DISCARD and e.value == 2

    def test_discard_missing_noop(self):
        original = {1, 2}
        js = JournalledSet(original)
        js.discard(5)  # not present
        assert js.edited is False
        assert js.journal == ()

    def test_multiple_edits_order(self):
        original = {1, 2}
        js = JournalledSet(original)
        js.add(3)
        js.discard(1)
        js.add(4)
        assert js.edited is True
        assert [e.type for e in js.journal] == [
            JournalledSetEditType.ADD,
            JournalledSetEditType.DISCARD,
            JournalledSetEditType.ADD,
        ]
        assert set(js) == {2, 3, 4}
        assert original == {1, 2}

    def test_iteration_reflects_changes_and_original_unchanged(self):
        original = {10, 20, 30}
        js = JournalledSet(original)
        js.add(40)
        js.discard(20)
        assert js.edited is True
        assert set(iter(js)) == {10, 30, 40}
        # Original set not modified
        assert original == {10, 20, 30}
