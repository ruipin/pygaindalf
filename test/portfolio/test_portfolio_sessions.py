"""Tests exercising portfolio session code paths via PortfolioManager.

These tests intentionally avoid using any bespoke session fixtures and instead
drive everything through a real `PortfolioManager` and its `session_manager`.

They validate ledger + transaction add/remove and reordering behaviors using
the journalling layer (JournalledMapping / JournalledSequence) across commits
and aborts.
"""

import datetime
from decimal import Decimal

import pytest
from iso4217 import Currency

from app.portfolio.manager import PortfolioManager
from app.portfolio.models.instrument import Instrument
from app.portfolio.models.ledger import Ledger
from app.portfolio.models.transaction import Transaction, TransactionType
from app.portfolio.journal.collections.sequence import JournalledSequence
from app.portfolio.journal.collections.mapping import JournalledMapping
from app.util.helpers.frozendict import frozendict


# --- Fixtures --------------------------------------------------------------------

@pytest.fixture()
def portfolio_manager() -> PortfolioManager:
    return PortfolioManager()

@pytest.fixture()
def portfolio(portfolio_manager: PortfolioManager):
    return portfolio_manager.portfolio

@pytest.fixture()
def session_manager(portfolio_manager: PortfolioManager):
    return portfolio_manager.session_manager


@pytest.mark.portfolio
@pytest.mark.session
class TestPortfolioSessions:
    def test_add_ledgers_commit(self, portfolio, session_manager):
        assert portfolio.ledgers == {}

        inst1 = Instrument(ticker="AAPL", currency=Currency("USD"))
        ledg1 = Ledger(instrument=inst1)

        inst2 = Instrument(ticker="MSFT", currency=Currency("USD"))
        ledg2 = Ledger(instrument=inst2)

        with session_manager(actor="tester", reason="add-ledgers") as s:
            # Access mapping via session (wrapped JournalledMapping)
            ledgers_map = portfolio.ledgers
            ledgers_map[ledg1.uid] = ledg1
            ledgers_map[ledg2.uid] = ledg2
            assert portfolio.dirty is True
            assert s.dirty is True

        # Session auto-commits on exit -> portfolio superseded
        p_new = portfolio.superseding
        assert p_new is not None and p_new is not portfolio
        assert ledg1.uid in p_new.ledgers and ledg2.uid in p_new.ledgers
        assert p_new.ledgers[ledg1.uid] is ledg1
        assert p_new.ledgers[ledg2.uid] is ledg2

    def test_add_and_remove_ledger_abort(self, portfolio, session_manager):
        inst = Instrument(ticker="GOOGL", currency=Currency("USD"))
        ledg = Ledger(instrument=inst)

        with session_manager(actor="tester", reason="add-then-abort") as s:
            ledgers_map = portfolio.ledgers
            ledgers_map[inst.uid] = ledg
            assert inst.uid in ledgers_map
            assert portfolio.dirty
            s.abort()  # abort edits
            assert not s.dirty
            # Still inside context, but edits cleared
            assert inst.uid not in portfolio.ledgers

        # After context, portfolio unchanged
        assert inst.uid not in portfolio.ledgers

    def test_remove_existing_ledger_commit(self, portfolio, session_manager, portfolio_manager):
        # Seed a ledger through update (no session needed for initial construction)
        inst = Instrument(ticker="ORCL", currency=Currency("USD"))
        ledg = Ledger(instrument=inst)
        p2 = portfolio.update(ledgers=frozendict({ledg.uid: ledg}))
        assert ledg.uid in p2.ledgers

        # Update manager to point to latest portfolio version so session sees it
        portfolio_manager.portfolio = p2

        with session_manager(actor="tester", reason="remove-ledger"):
            mapping = p2.ledgers
            del mapping[ledg.uid]
            assert ledg.uid not in mapping

        p3 = p2.superseding
        assert p3 is not None and inst.uid not in p3.ledgers

    def test_add_transactions_and_reorder_commit(self, portfolio, session_manager, portfolio_manager):
        inst = Instrument(ticker="TSLA", currency=Currency("USD"))
        ledg = Ledger(instrument=inst)
        p2 = portfolio.update(ledgers=frozendict({ledg.uid: ledg}))

        portfolio_manager.portfolio = p2

        with session_manager(actor="tester", reason="tx-add-reorder") as s:
            # Create three tx
            t1 = Transaction(
                instrument_uid=inst.uid,
                type=TransactionType.BUY,
                date=datetime.date(2025, 1, 1),
                quantity=Decimal("10"),
                consideration=Decimal("1000"),
            )
            t2 = Transaction(
                instrument_uid=inst.uid,
                type=TransactionType.SELL,
                date=datetime.date(2025, 1, 2),
                quantity=Decimal("4"),
                consideration=Decimal("420"),
            )
            t3 = Transaction(
                instrument_uid=inst.uid,
                type=TransactionType.BUY,
                date=datetime.date(2025, 1, 3),
                quantity=Decimal("6"),
                consideration=Decimal("630"),
            )

            # Access ledger transactions (JournalledSequence)
            tx_seq = ledg.transactions
            assert len(tx_seq) == 0
            tx_seq.insert(0, t1)
            tx_seq.insert(1, t2)
            tx_seq.insert(2, t3)
            assert list(tx_seq) == [t1, t2, t3]

            # Reorder: move last to front
            tx_seq[0], tx_seq[2] = tx_seq[2], tx_seq[0]
            assert list(tx_seq) == [t3, t2, t1]
            assert s.dirty and ledg.dirty and p2.dirty

        # After auto-commit, get superseding portfolio & ledger
        p3 = p2.superseding
        assert p3 is not None
        new_ledger = p3.ledgers[ledg.uid]
        assert new_ledger is not ledg
        assert list(new_ledger.transactions) == [t3, t2, t1]

    def test_remove_transaction_abort(self, portfolio, session_manager, portfolio_manager):
        inst = Instrument(ticker="NVDA", currency=Currency("USD"))
        t1 = Transaction(
            instrument_uid=inst.uid,
            type=TransactionType.BUY,
            date=datetime.date(2025, 2, 1),
            quantity=Decimal("5"),
            consideration=Decimal("2500"),
        )
        t2 = Transaction(
            instrument_uid=inst.uid,
            type=TransactionType.BUY,
            date=datetime.date(2025, 2, 2),
            quantity=Decimal("3"),
            consideration=Decimal("1500"),
        )
        ledg = Ledger(instrument=inst, transactions=(t1, t2))
        p2 = portfolio.update(ledgers=frozendict({ledg.uid: ledg}))

        portfolio_manager.portfolio = p2

        with session_manager(actor="tester", reason="tx-remove-abort") as s:
            tx_seq = ledg.transactions
            assert list(tx_seq) == [t1, t2]
            del tx_seq[0]
            assert list(tx_seq) == [t2]
            assert s.dirty
            s.abort()
            assert not s.dirty
            # Reverted view inside session
            assert list(ledg.transactions) == [t1, t2]

        # After abort session exit, no change
        assert list(p2.ledgers[ledg.uid].transactions) == [t1, t2]

    def test_reorder_transactions_commit(self, portfolio, session_manager, portfolio_manager):
        inst = Instrument(ticker="IBM", currency=Currency("USD"))
        t1 = Transaction(
            instrument_uid=inst.uid,
            type=TransactionType.BUY,
            date=datetime.date(2025, 3, 1),
            quantity=Decimal("1"),
            consideration=Decimal("100"),
        )
        t2 = Transaction(
            instrument_uid=inst.uid,
            type=TransactionType.BUY,
            date=datetime.date(2025, 3, 2),
            quantity=Decimal("2"),
            consideration=Decimal("210"),
        )
        t3 = Transaction(
            instrument_uid=inst.uid,
            type=TransactionType.BUY,
            date=datetime.date(2025, 3, 3),
            quantity=Decimal("3"),
            consideration=Decimal("330"),
        )
        ledg = Ledger(instrument=inst, transactions=(t1, t2, t3))
        p2 = portfolio.update(ledgers=frozendict({ledg.uid: ledg}))

        portfolio_manager.portfolio = p2
        assert portfolio_manager.portfolio is p2

        with session_manager(actor="tester", reason="reorder-commit"):
            seq = ledg.transactions
            # Reverse order
            seq[0], seq[2] = seq[2], seq[0]
            assert list(seq) == [t3, t2, t1]

        p3 = p2.superseding
        assert p3 is not None
        new_ledger = p3.ledgers[ledg.uid]
        assert list(new_ledger.transactions) == [t3, t2, t1]

