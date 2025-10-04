# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest

from app.portfolio.collections.journalled.sequence import (
    JournalledSequence,
    JournalledSequenceEditType,
)


@pytest.mark.portfolio_collections
@pytest.mark.journalled_collections
class TestJournalledSequence:
    def test_no_edit_pass_through(self):
        original = [1, 2, 3]
        js = JournalledSequence(original)
        assert js.edited is False
        assert len(js) == len(original)
        assert js[0] == 1  # pass-through before edits
        # journal should be empty before any edits
        assert js.journal == ()

    def test_setitem_triggers_copy_and_journal(self):
        original = [1, 2, 3]
        js = JournalledSequence(original)
        js[1] = 42
        assert js.edited is True
        assert original[1] == 2  # original unchanged
        assert js[1] == 42
        assert len(js.journal) == 1
        e = js.journal[0]
        assert e.type is JournalledSequenceEditType.SETITEM
        assert e.index == 1 and e.value == 42

    def test_delitem(self):
        original = [1, 2, 3]
        js = JournalledSequence(original)
        del js[0]
        assert js.edited is True
        assert js[0] == 2
        assert len(js) == 2
        assert len(js.journal) == 1
        e = js.journal[0]
        assert e.type is JournalledSequenceEditType.DELITEM
        assert e.index == 0

    def test_insert(self):
        original = [1, 2, 3]
        js = JournalledSequence(original)
        js.insert(1, 99)
        assert js.edited is True
        assert js[1] == 99
        assert len(js) == 4
        e = js.journal[0]
        assert e.type is JournalledSequenceEditType.INSERT
        assert e.index == 1 and e.value == 99

    def test_multiple_edits_order(self):
        original = [10, 20]
        js = JournalledSequence(original)
        js.insert(1, 15)
        js[0] = 5
        del js[2]  # delete 20
        assert [e.type for e in js.journal] == [
            JournalledSequenceEditType.INSERT,
            JournalledSequenceEditType.SETITEM,
            JournalledSequenceEditType.DELITEM,
        ]
        assert list(js) == [5, 15]

    def test_slice_get(self):
        original = [1, 2, 3]
        js = JournalledSequence(original)

        try:
            _ = js[0:2]
        except NotImplementedError:
            pytest.xfail("Sliced read access not implemented yet")
        else:
            pytest.fail("Sliced read access not implemented yet but did not raise NotImplementedError")

    def test_slice_set(self):
        original = [1, 2, 3, 4]
        js = JournalledSequence(original)
        js[1:3] = [9, 9]
        assert list(js) == [1, 9, 9, 4]
        assert js.journal[0].type is JournalledSequenceEditType.SETITEM
        assert isinstance(js.journal[0].index, slice)

    def test_extended_multiple_edits(self):
        """More comprehensive multi-edit scenario covering set, insert, delete and slice set."""
        original = [10, 20, 30, 40, 50]
        js = JournalledSequence(original)

        # 1. set existing index
        js[1] = 21
        # 2. insert in the middle (after index 2 original position)
        js.insert(3, 35)
        # 3. delete first element
        del js[0]
        # 4. slice set (replace two consecutive items)
        js[1:3] = [300, 350]

        # Journal assertions
        assert len(js.journal) == 4
        j0, j1, j2, j3 = js.journal
        assert (j0.type, j0.index, j0.value) == (JournalledSequenceEditType.SETITEM, 1, 21)
        assert (j1.type, j1.index, j1.value) == (JournalledSequenceEditType.INSERT, 3, 35)
        assert (j2.type, j2.index, j2.value) == (JournalledSequenceEditType.DELITEM, 0, None)
        assert j3.type is JournalledSequenceEditType.SETITEM and isinstance(j3.index, slice)
        assert j3.value == (300, 350)

        # Final sequence state
        assert list(js) == [21, 300, 350, 40, 50]
        # Original must remain unchanged
        assert original == [10, 20, 30, 40, 50]
