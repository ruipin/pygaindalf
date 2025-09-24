# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest

from iso4217 import Currency

from app.portfolio.journal.session_manager import SessionManager
from app.portfolio.journal.session import Session

from app.portfolio.models.root import EntityRoot
from app.portfolio.models.instrument.instrument import Instrument
from app.portfolio.models.instrument.instrument_journal import InstrumentJournal


# --- Fixtures --------------------------------------------------------------------
@pytest.fixture(scope='function')
def instrument(entity_root: EntityRoot) -> Instrument:
    with entity_root.session_manager(actor="instrument fixture", reason="fixture setup"):
        instrument = entity_root.root = Instrument(ticker="AAPL", currency=Currency("USD"))
    return instrument


# --- Tests -----------------------------------------------------------------------

@pytest.mark.portfolio
@pytest.mark.instrument
@pytest.mark.session
class TestInstrumentJournalWithSessions:
    def test_accessing_journal_without_session_raises(self, instrument: Instrument):
        assert instrument.session_manager.in_session is False
        with pytest.raises(RuntimeError):
            _ = instrument.journal

    def test_stage_updates_via_journal_methods_and_entity_unchanged(self, instrument: Instrument, session_manager: SessionManager):
        with session_manager(actor="tester", reason="stage") as s:
            assert isinstance(s, Session)

            # Acquire journal and stage updates via API methods
            from app.util.helpers import generics
            from app.portfolio.models.entity import Entity
            j: InstrumentJournal = instrument.journal
            assert isinstance(j, InstrumentJournal)

            # Baseline
            assert instrument.ticker == "AAPL"
            assert instrument.currency == Currency("USD")

            # Stage changes (entity must not be mutated yet)
            j.set_field("ticker", "MSFT")
            j.set_field("currency", Currency("EUR"))

            # Journal reflects updates
            assert j.get_field("ticker") == "MSFT"
            assert j.get_field("currency") == Currency("EUR")
            assert j.is_field_updated("ticker") is True
            assert j.is_field_updated("currency") is True
            assert j.dirty is True

            # Entity remains unchanged until commit is implemented
            assert instrument.ticker == "AAPL"
            assert instrument.currency == Currency("USD")

            # Abort clears journals (and dirtiness)
            s.abort()
            assert s.dirty is False

    def test_identity_revert_clears_update(self, instrument: Instrument, session_manager: SessionManager):
        with session_manager(actor="tester", reason="revert") as s:
            j = instrument.journal

            # Stage a change
            original_currency = j.get_original_field("currency")
            j.set_field("currency", Currency("GBP"))
            assert j.is_field_updated("currency") is True
            assert j.dirty is True

            # Revert by identity to the exact original object -> clears update
            j.set_field("currency", original_currency)
            assert j.is_field_updated("currency") is False
            assert j.dirty is False

            s.abort()

    def test_attribute_forbids_name_changes(self, instrument: Instrument, session_manager: SessionManager):
        with pytest.raises(ValueError, match='Updating the entity cannot change its instance name'):
            with session_manager(actor="tester", reason="attr-style"):
                j = instrument.journal

                # Expected new behavior: write via journal attributes instead of entity
                j.ticker = "TSLA"
                j.currency = Currency("GBP")

                assert j.get_field("ticker") == "TSLA"
                assert j.get_field("currency") == Currency("GBP")
                assert instrument.ticker == "AAPL"  # unchanged until commit
                assert instrument.currency == Currency("USD")
