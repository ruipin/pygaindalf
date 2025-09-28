# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest
from typing import Any, Iterator, override, ClassVar
from pydantic import Field, PrivateAttr, ValidationError, BaseModel, InstanceOf, ConfigDict

from app.portfolio.journal.session_manager import SessionManager
from app.portfolio.models.root import EntityRoot
from app.portfolio.journal.session import Session
from app.portfolio.journal.entity_journal import EntityJournal
from app.portfolio.collections.journalled.sequence import JournalledSequence
from app.portfolio.collections.journalled.mapping import JournalledMapping
from app.portfolio.models.entity.incrementing_uid_entity import IncrementingUidEntity
from app.portfolio.util.superseded import SupersededError


# --- Sample Entity -----------------------------------------------------------------
class SampleEntity(IncrementingUidEntity):
    """Simple concrete entity used for journaling tests.

    Fields deliberately include scalars and mutable collection types to exercise
    journal wrapping and identity-based update clearing.
    """

    value: int
    items: list[int] = Field(default_factory=lambda: [1, 2, 3].copy())
    meta: dict[str, int] = Field(default_factory=lambda: {"a": 1, "b": 2}.copy())
    data: list[int] = Field(default_factory=lambda: [10, 20].copy())
    note: str = Field(default="initial")


# --- Fixtures --------------------------------------------------------------------
@pytest.fixture(scope='function')
def entity(entity_root: EntityRoot) -> SampleEntity:
    with entity_root.session_manager(actor="entity fixture", reason="fixture setup"):
        entity = entity_root.root = SampleEntity(value=1)
    return entity


# --- Tests -----------------------------------------------------------------------

@pytest.mark.journal
@pytest.mark.session
class TestSessionEntityJournal:
    def test_write_without_session_fails(self, entity: SampleEntity):
        # Ensure no active session
        assert entity.session_manager.in_session is False
        with pytest.raises(ValidationError):  # pydantic frozen model raises
            entity.value = 2

    def test_write_inside_session_and_original_value(self, entity: SampleEntity, session_manager: SessionManager):
        with session_manager(actor="tester", reason="unit-test") as s:
            assert entity.session_manager.in_session is True

            assert entity.value == 1
            assert entity.journal.value == 1

            entity.journal.value = 42  # journal set, not pydantic mutation
            assert entity.journal.value == 42  # read sees tentative update
            assert entity.value == 1 # but entity does not change
            j = entity.journal
            assert isinstance(j, EntityJournal)
            assert j.dirty is True
            assert s.dirty is True

            # Cleanup: abort session to clear updates
            s.abort()
            assert s.dirty is False
            assert entity.value == 1  # reverted view (still in session but update cleared)

    def test_noop_same_instance_and_revert_clears_update(self, entity: SampleEntity, session_manager: SessionManager):
        lst_original = entity.data
        assert isinstance(lst_original, list)

        with session_manager(actor="tester", reason="unit-test") as s:
            lst_j = entity.journal.data
            assert isinstance(lst_j, JournalledSequence)

            # Write identical (same identity) object to field 'meta'
            meta_original = entity.journal.get_original_field("meta")
            assert isinstance(meta_original, dict)
            entity.journal.meta = meta_original  # identity -> no update created
            assert not entity.journal.is_field_edited("meta")

            # Modify field with a different object
            new_meta = {"a": 10, "b": 2}
            entity.journal.meta = new_meta
            assert entity.journal.meta is new_meta
            assert entity.dirty is True

            # Revert to original identity -> clears update
            entity.journal.meta = meta_original
            assert not entity.journal.is_field_edited("meta")
            assert entity.dirty is False

            s.abort()

    def test_read_collection_wraps_sequence_and_mapping(self, entity: SampleEntity, session_manager: SessionManager):
        with session_manager(actor="tester", reason="unit-test") as s:
            items_wrapped = entity.journal.items
            meta_wrapped = entity.journal.meta

            assert isinstance(items_wrapped, JournalledSequence)
            assert isinstance(meta_wrapped, JournalledMapping)

            # Mutate wrapped collections
            items_wrapped.insert(0, 99)
            meta_wrapped["c"] = 3

            assert items_wrapped.edited is True
            assert meta_wrapped.edited is True
            assert entity.dirty is True

            s.abort()
            assert entity.dirty is False

    def test_start_then_abort_no_edits_noop(self, entity : SampleEntity, session_manager: SessionManager):
        with session_manager(actor="tester", reason="noop") as s:
            assert s.dirty is False
            s.abort()  # no edits -> no-op
            assert s.dirty is False
            # still active
            assert session_manager.in_session is True
        assert session_manager.in_session is False

    def test_start_then_abort_with_edits_clears(self, entity: SampleEntity, session_manager: SessionManager):
        with session_manager(actor="tester", reason="unit-test") as s:
            entity.journal.value = 5
            assert s.dirty is True
            s.abort()  # clears journals
            assert s.dirty is False
            assert entity.value == 1  # reverted

    def test_session_commit_without_changes_noop(self, entity : SampleEntity, session_manager: SessionManager):
        with session_manager(actor="tester", reason="noop-commit") as s:
            assert s.dirty is False
            s.commit()  # should not raise (no changes)
            assert s.dirty is False

    def test_session_commit_with_changes_applies_and_restarts(self, entity: SampleEntity, session_manager: SessionManager):
        with session_manager(actor="tester", reason="unit-test") as s:
            current_version = entity.version
            entity.journal.value = 99
            assert entity.dirty is True
            s.commit()  # expected to apply changes & potentially allow continued session (future behavior)

            assert entity.superseded is True

            # Expectations once implemented:
            new_entity = SampleEntity.by_uid_or_none(entity.uid)
            assert new_entity is not None, "Expected a new entity version after commit"
            assert new_entity.version == current_version + 1
            assert new_entity.value == 99
            assert entity.superseded is True

    def test_session_end_with_changes_updates_entities(self, entity: SampleEntity, session_manager: SessionManager):
        with session_manager(actor="tester", reason="unit-test") as s:
            v_old = entity.version
            entity.journal.note = "updated"
            assert entity.dirty is True
            s.end()  # should commit then mark ended
            assert s.ended is True

            new_entity = SampleEntity.by_uid_or_none(entity.uid)
            assert new_entity is not None, "Expected a new entity version after end commit"
            assert new_entity.version == v_old + 1
            assert new_entity.superseded is False
            assert new_entity.note == "updated"
            assert entity.superseded is True

    def test_using_session_after_end_fails(self, entity: SampleEntity, session_manager: SessionManager):
        with session_manager(actor="tester", reason="unit-test") as s:
            s.end()
            assert s.ended is True
            with pytest.raises(SupersededError):
                s.commit()
            with pytest.raises(SupersededError):
                s.get_entity_journal(entity=entity)

    def test_using_invalid_journal_fails(self, entity: SampleEntity, session_manager: SessionManager):
        with session_manager(actor="tester", reason="unit-test") as s:
            j = entity.journal
            j.mark_superseded()
            with pytest.raises(SupersededError):
                j.get_field("value")


    # --- Additional behavior -----------------------------------------------------------------
    def test_collection_edits_do_not_mutate_originals(self, entity: SampleEntity, session_manager: SessionManager):
        with session_manager(actor="tester", reason="unit-test") as s:
            assert isinstance(entity.items, list)
            assert isinstance(entity.meta, dict)

            # Perform edits on wrapped structures
            items_wrapped = entity.journal.items
            meta_wrapped = entity.journal.meta
            items_wrapped[1] = 200
            meta_wrapped["a"] = 10

            # Originals unchanged
            assert entity.items[1] == 2
            assert entity.meta["a"] == 1

            # Abort -> changes discarded
            s.abort()
            assert entity.value == 1
            assert entity.items[1] == 2
            assert entity.meta["a"] == 1
