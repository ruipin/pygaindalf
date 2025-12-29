# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest

from app.portfolio.journal.session import Session
from app.portfolio.journal.session_manager import SessionManager
from app.portfolio.models.instrument import Instrument
from app.portfolio.models.instrument.instrument_journal import InstrumentJournal
from app.portfolio.models.instrument.instrument_type import InstrumentType
from app.portfolio.models.root import EntityRoot
from app.util.helpers.currency import Currency


# --- Fixtures --------------------------------------------------------------------
@pytest.fixture
def instrument(entity_root: EntityRoot) -> Instrument:
    with entity_root.session_manager(actor="instrument fixture", reason="fixture setup"):
        entity = entity_root.root = Instrument(ticker="AAPL", type=InstrumentType.EQUITY, currency=Currency("USD"))
    return entity


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
            assert j.is_field_edited("ticker") is True
            assert j.is_field_edited("currency") is True
            assert j.dirty is True

            # EntityRecord remains unchanged until commit is implemented
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
            assert j.is_field_edited("currency") is True
            assert j.dirty is True

            # Revert by identity to the exact original object -> clears update
            j.set_field("currency", original_currency)
            assert j.is_field_edited("currency") is False
            assert j.dirty is False

            s.abort()

    def test_attribute_forbids_name_changes(self, instrument: Instrument, session_manager: SessionManager):
        with (
            pytest.raises(ValueError, match="Updating the entity record cannot change its instance name"),
            session_manager(actor="tester", reason="attr-style", exit_on_exception=False),
        ):
            j = instrument.journal

            # Write via journal attributes
            j.ticker = "TSLA"
            j.currency = Currency("GBP")

            assert j.get_field("ticker") == "TSLA"
            assert j.get_field("currency") == Currency("GBP")
            assert instrument.ticker == "AAPL"  # unchanged until commit
            assert instrument.currency == Currency("USD")
