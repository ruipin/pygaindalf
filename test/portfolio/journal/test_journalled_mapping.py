# SPDX-License-Identifier: GPLv3-or-later
# Tests for JournalledMapping copy-on-write and journaling

import pytest

from app.portfolio.journal.collections.mapping import JournalledMapping, JournalledMappingEditType


@pytest.mark.journal
@pytest.mark.portfolio
@pytest.mark.journalled_data_structures
class TestJournalledMapping:
    def test_no_edit_pass_through(self):
        original = {"a":1, "b":2}
        jm = JournalledMapping(original)
        assert jm.edited is False
        assert jm["a"] == 1
        assert jm._mapping is None
        assert len(jm) == 2

    def test_setitem_triggers_copy_and_journal(self):
        original = {"a":1}
        jm = JournalledMapping(original)
        jm["a"] = 10
        assert jm.edited is True
        assert jm._mapping is not None
        assert original["a"] == 1
        assert jm["a"] == 10
        assert len(jm._journal) == 1
        e = jm._journal[0]
        assert e.type is JournalledMappingEditType.SETITEM
        assert e.key == "a" and e.value == 10

    def test_delitem(self):
        original = {"a":1, "b":2}
        jm = JournalledMapping(original)
        del jm["a"]
        assert jm.edited is True
        assert "a" not in jm
        assert len(jm) == 1
        e = jm._journal[0]
        assert e.type is JournalledMappingEditType.DELITEM
        assert e.key == "a"

    def test_multiple_edits_order(self):
        original = {"x":1, "y":2}
        jm = JournalledMapping(original)
        jm["z"] = 3
        jm["x"] = 5
        del jm["y"]
        assert [e.type for e in jm._journal] == [
            JournalledMappingEditType.SETITEM,
            JournalledMappingEditType.SETITEM,
            JournalledMappingEditType.DELITEM,
        ]
        assert jm["x"] == 5 and jm["z"] == 3 and "y" not in jm

    def test_extended_multiple_edits(self):
        """More comprehensive multi-edit scenario covering multiple sets and a delete."""
        original = {"a":1, "b":2, "c":3}
        jm = JournalledMapping(original)

        # 1. add new key
        jm["d"] = 4
        # 2. update existing key
        jm["b"] = 20
        # 3. delete a key
        del jm["a"]
        # 4. update another existing key
        jm["c"] = 30

        # Journal assertions
        assert len(jm._journal) == 4
        j0, j1, j2, j3 = jm._journal
        assert (j0.type, j0.key, j0.value) == (JournalledMappingEditType.SETITEM, "d", 4)
        assert (j1.type, j1.key, j1.value) == (JournalledMappingEditType.SETITEM, "b", 20)
        assert (j2.type, j2.key, j2.value) == (JournalledMappingEditType.DELITEM, "a", None)
        assert (j3.type, j3.key, j3.value) == (JournalledMappingEditType.SETITEM, "c", 30)

        # Final mapping state
        assert dict(jm) == {"b":20, "c":30, "d":4}
        # Original must remain unchanged
        assert original == {"a":1, "b":2, "c":3}

