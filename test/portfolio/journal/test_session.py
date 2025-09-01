# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest
from typing import Any, Iterator, override, ClassVar
from pydantic import Field, PrivateAttr, ValidationError, BaseModel, InstanceOf, ConfigDict

from app.util.mixins.models import LoggableHierarchicalModel
from app.portfolio.journal.session_manager import SessionManager
from app.portfolio.journal.session import JournalSession
from app.portfolio.journal.entity import EntityJournal
from app.portfolio.journal.collections.sequence import JournalledSequence
from app.portfolio.journal.collections.mapping import JournalledMapping
from app.portfolio.models.entity.incrementing_uid_entity import IncrementingUidEntity
from app.portfolio.models.entity.superseded import SupersededError


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

class SampleEntityManager(LoggableHierarchicalModel):
    model_config = ConfigDict(
        extra='forbid',
        validate_assignment=True,
    )

    entity : InstanceOf[SampleEntity] = Field(default_factory=lambda: SampleEntity(value=1))
    session_manager : InstanceOf[SessionManager] = Field(default_factory=SessionManager)

    def refresh_entities(self):
        superseding = self.entity.superseding
        assert superseding is not None
        self.entity = superseding


# --- Fixtures --------------------------------------------------------------------
@pytest.fixture()
def entity_manager() -> SampleEntityManager:
    return SampleEntityManager()

@pytest.fixture()
def session_manager(entity_manager : SampleEntityManager) -> SessionManager:
    return entity_manager.session_manager

@pytest.fixture(scope='function')
def entity(entity_manager: SampleEntityManager) -> SampleEntity:
    return entity_manager.entity


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
            original = entity.journal.get_original_field("value")
            assert original == 1

            entity.value = 42  # journal set, not pydantic mutation
            assert entity.value == 42  # read sees tentative update
            j = entity.journal
            assert isinstance(j, EntityJournal)
            assert j.get_original_field("value") == 1  # original unaffected
            assert j.dirty is True
            assert s.dirty is True

            # Cleanup: abort session to clear updates
            s.abort()
            assert s.dirty is False
            assert entity.value == 1  # reverted view (still in session but update cleared)

    def test_noop_same_instance_and_revert_clears_update(self, entity: SampleEntity, session_manager: SessionManager):
        with session_manager(actor="tester", reason="unit-test") as s:
            lst_original = entity.data  # triggers wrapping? first access -> JournalledSequence
            # Access during session -> wrapper placement; but list field is a list -> returns JournalledSequence
            assert isinstance(lst_original, JournalledSequence)

            # Write identical (same identity) object to field 'meta'
            meta_original = entity.journal.get_original_field("meta")
            assert isinstance(meta_original, dict)
            entity.meta = meta_original  # identity -> no update created
            assert not entity.journal.updated("meta")

            # Modify field with a different object
            new_meta = {"a": 10, "b": 2}
            entity.meta = new_meta
            assert entity.journal.get('meta') is new_meta
            assert entity.dirty is True

            # Revert to original identity -> clears update
            entity.meta = meta_original
            assert not entity.journal.updated("meta")
            assert entity.dirty is False

            s.abort()

    def test_read_collection_wraps_sequence_and_mapping(self, entity: SampleEntity, session_manager: SessionManager):
        with session_manager(actor="tester", reason="unit-test") as s:
            items_wrapped = entity.items
            meta_wrapped = entity.meta

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

    def test_start_then_abort_no_edits_noop(self, session_manager: SessionManager):
        with session_manager(actor="tester", reason="noop") as s:
            assert s.dirty is False
            s.abort()  # no edits -> no-op
            assert s.dirty is False
            # still active
            assert session_manager.in_session is True
        assert session_manager.in_session is False

    def test_start_then_abort_with_edits_clears(self, entity: SampleEntity, session_manager: SessionManager):
        with session_manager(actor="tester", reason="unit-test") as s:
            entity.value = 5
            assert s.dirty is True
            s.abort()  # clears journals
            assert s.dirty is False
            assert entity.value == 1  # reverted

    def test_session_commit_without_changes_noop(self, session_manager: SessionManager):
        with session_manager(actor="tester", reason="noop-commit") as s:
            assert s.dirty is False
            s.commit()  # should not raise (no changes)
            assert s.dirty is False

    def test_session_commit_with_changes_applies_and_restarts(self, entity: SampleEntity, session_manager: SessionManager):
        with session_manager(actor="tester", reason="unit-test") as s:
            current_version = entity.version
            entity.value = 99
            assert entity.dirty is True
            s.commit()  # expected to apply changes & potentially allow continued session (future behavior)

            assert entity.superseded is True
            print(entity.entity_log.entity)

            # Expectations once implemented:
            new_entity = SampleEntity.by_uid(entity.uid)
            assert new_entity is not None, "Expected a new entity version after commit"
            assert new_entity.version == current_version + 1
            assert new_entity.value == 99
            assert entity.superseded is True

    def test_session_end_with_changes_updates_entities(self, entity: SampleEntity, session_manager: SessionManager):
        with session_manager(actor="tester", reason="unit-test") as s:
            v_old = entity.version
            entity.note = "updated"
            assert entity.dirty is True
            s.end()  # should commit then mark ended
            assert s.ended is True

            new_entity = SampleEntity.by_uid(entity.uid)
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

    def test_using_ended_journal_fails(self, entity: SampleEntity, session_manager: SessionManager):
        with session_manager(actor="tester", reason="unit-test") as s:
            # Placeholder: once journal.commit/end implemented, accessing after end should raise
            j = entity.journal
            # Simulate end (future: j.commit() or j.end())
            object.__setattr__(j, "_ended", True)  # force ended state for placeholder
            with pytest.raises(SupersededError):
                j.get("value")


    # --- Additional behavior -----------------------------------------------------------------
    def test_collection_edits_do_not_mutate_originals(self, entity: SampleEntity, session_manager: SessionManager):
        with session_manager(actor="tester", reason="unit-test") as s:
            original_items_ref = entity.journal.get_original_field("items")
            original_meta_ref = entity.journal.get_original_field("meta")
            assert isinstance(original_items_ref, list)
            assert isinstance(original_meta_ref, dict)

            # Perform edits on wrapped structures
            items_wrapped = entity.items
            meta_wrapped = entity.meta
            items_wrapped[1] = 200
            meta_wrapped["a"] = 10

            # Originals unchanged
            assert original_items_ref[1] == 2
            assert original_meta_ref["a"] == 1

            # Abort -> changes discarded
            s.abort()
            assert entity.value == 1
            assert original_items_ref[1] == 2
            assert original_meta_ref["a"] == 1
