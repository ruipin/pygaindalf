"""Tests exercising portfolio session code paths via PortfolioRoot.

These tests intentionally avoid using any bespoke session fixtures and instead
drive everything through a real `PortfolioRoot` and its `session_manager`.

They validate ledger + transaction add/remove and reordering behaviors using
the journalling layer (JournalledMapping / JournalledSequence) across commits
and aborts.
"""

import datetime
from decimal import Decimal

import pytest
from iso4217 import Currency
from collections.abc import MutableSet, Set

from app.portfolio.root import PortfolioRoot
from app.portfolio.models.instrument.instrument import Instrument
from app.portfolio.models.ledger.ledger import Ledger
from app.portfolio.models.transaction.transaction import Transaction, TransactionType
from app.portfolio.models.portfolio import Portfolio
from app.portfolio.collections.journalled.sequence import JournalledSequence  # noqa: F401 (documentation/reference)
from app.portfolio.collections.journalled.mapping import JournalledMapping  # noqa: F401 (documentation/reference)


# --- Fixtures --------------------------------------------------------------------

@pytest.fixture()
def portfolio_manager() -> PortfolioRoot:
    return PortfolioRoot()

@pytest.fixture()
def portfolio(portfolio_manager: PortfolioRoot):
    return portfolio_manager.portfolio

@pytest.fixture()
def session_manager(portfolio_manager: PortfolioRoot):
    return portfolio_manager.session_manager


@pytest.mark.portfolio
@pytest.mark.session
class TestPortfolioSessions:
    def test_add_ledgers_commit(self, portfolio : Portfolio, session_manager):
        assert portfolio.ledgers == set()
        assert len(portfolio.ledgers) == 0

        inst1 = Instrument(ticker="AAPL", currency=Currency("USD"))
        ledg1 = Ledger(instrument_uid=inst1.uid)

        inst2 = Instrument(ticker="MSFT", currency=Currency("USD"))
        ledg2 = Ledger(instrument_uid=inst2.uid)

        with session_manager(actor="tester", reason="add-ledgers") as s:
            # Access mutable set via the portfolio's journal
            ledgers_set = portfolio.journal.ledgers
            ledgers_set.add(ledg1)
            ledgers_set.add(ledg2)
            assert portfolio.dirty is True
            assert s.dirty is True

        # Session auto-commits on exit -> portfolio superseded
        p_new = portfolio.superseding
        assert p_new is not None and p_new is not portfolio
        # Membership only; set holds ledgers
        assert ledg1 in p_new.ledgers and ledg2 in p_new.ledgers
        # Retrieve via portfolio __getitem__ using Instrument or Uid
        assert p_new[inst1] is ledg1
        assert p_new[inst2] is ledg2

    def test_add_and_remove_ledger_abort(self, portfolio : Portfolio, session_manager):
        inst = Instrument(ticker="GOOGL", currency=Currency("USD"))
        ledg = Ledger(instrument_uid=inst.uid)

        with session_manager(actor="tester", reason="add-then-abort") as s:
            ledgers_set = portfolio.journal.ledgers
            ledgers_set.add(ledg)
            assert ledg in ledgers_set
            assert portfolio.dirty
            s.abort()  # abort edits
            assert not s.dirty
            # Still inside context, but edits cleared
            assert ledg not in portfolio.ledgers

        # After context, portfolio unchanged
        assert ledg not in portfolio.ledgers

    def test_remove_existing_ledger_commit(self, portfolio : Portfolio, session_manager, portfolio_manager):
        # Seed a ledger through update (no session needed for initial construction)
        inst = Instrument(ticker="ORCL", currency=Currency("USD"))
        ledg = Ledger(instrument_uid=inst.uid)
        p2 = portfolio.update(ledger_uids={ledg.uid})
        assert ledg in p2.ledgers

        # Update manager to point to latest portfolio version so session sees it
        portfolio_manager.portfolio = p2

        with session_manager(actor="tester", reason="remove-ledger"):
            ledgers_set = p2.journal.ledgers
            ledgers_set.discard(ledg)
            assert ledg not in ledgers_set

        p3 = p2.superseding
        assert p3 is not None and ledg not in p3.ledgers

    def test_add_transactions_commit_and_ordering(self, portfolio : Portfolio, session_manager, portfolio_manager):
        inst = Instrument(ticker="TSLA", currency=Currency("USD"))
        ledg = Ledger(instrument_uid=inst.uid)
        p2 = portfolio.update(ledger_uids={ledg.uid})

        portfolio_manager.portfolio = p2

        with session_manager(actor="tester", reason="tx-add-reorder") as s:
            # Create three txns
            t1 = Transaction(
                type=TransactionType.BUY,
                date=datetime.date(2025, 1, 1),
                quantity=Decimal("10"),
                consideration=Decimal("1000"),
            )
            t2 = Transaction(
                type=TransactionType.SELL,
                date=datetime.date(2025, 1, 2),
                quantity=Decimal("4"),
                consideration=Decimal("420"),
            )
            t3 = Transaction(
                type=TransactionType.BUY,
                date=datetime.date(2025, 1, 3),
                quantity=Decimal("6"),
                consideration=Decimal("630"),
            )

            # Access ledger transactions via the journal (mutable ordered set view)
            assert ledg.in_session
            # Entities expose frozen sets; journal exposes mutable proxies
            assert isinstance(ledg.transaction_uids, Set) and not isinstance(ledg.transaction_uids, MutableSet)
            tx_set = ledg.journal.transactions
            assert len(tx_set) == 0
            # Add transactions (order determined by date automatically)
            tx_set.add(t2)
            tx_set.add(t3)
            tx_set.add(t1)
            # Ordering should be by date ascending -> t1, t2, t3
            assert len(tx_set) == 3
            assert list(tx_set) == [t1, t2, t3]
            assert s.dirty and ledg.dirty and p2.dirty

        # After auto-commit, get superseding portfolio & ledger
        p3 = p2.superseding
        assert p3 is not None
        new_ledger = p3[ledg.uid]
        assert new_ledger is not ledg
        # Persisted ordering by date
        assert list(new_ledger.transactions) == [t1, t2, t3]

    def test_remove_transaction_abort(self, portfolio : Portfolio, session_manager, portfolio_manager):
        inst = Instrument(ticker="NVDA", currency=Currency("USD"))
        t1 = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 2, 1),
            quantity=Decimal("5"),
            consideration=Decimal("2500"),
        )
        t2 = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 2, 2),
            quantity=Decimal("3"),
            consideration=Decimal("1500"),
        )
        ledg = Ledger(instrument_uid=inst.uid, transaction_uids={t1.uid, t2.uid})
        p2 = portfolio.update(ledger_uids={ledg.uid})

        portfolio_manager.portfolio = p2

        with session_manager(actor="tester", reason="tx-remove-abort") as s:
            tx_set = ledg.journal.transactions
            # Date ordering t1 (Feb 1) then t2 (Feb 2)
            assert list(tx_set) == [t1, t2]
            tx_set.discard(t1)
            assert list(tx_set) == [t2]
            assert s.dirty
            s.abort()
            assert not s.dirty
            # Reverted view inside session
            assert list(ledg.transactions) == [t1, t2]

        # After abort session exit, no change
        # Retrieve original ledger via indexing
        assert list(p2[ledg.uid].transactions) == [t1, t2]

    def test_reorder_transactions_commit(self, portfolio : Portfolio, session_manager, portfolio_manager):
        inst = Instrument(ticker="IBM", currency=Currency("USD"))
        t1 = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 3, 1),
            quantity=Decimal("1"),
            consideration=Decimal("100"),
        )
        t2 = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 3, 2),
            quantity=Decimal("2"),
            consideration=Decimal("210"),
        )
        t3 = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 3, 3),
            quantity=Decimal("3"),
            consideration=Decimal("330"),
        )
        ledg = Ledger(instrument_uid=inst.uid, transaction_uids={t1.uid, t2.uid, t3.uid})
        p2 = portfolio.update(ledger_uids={ledg.uid})

        portfolio_manager.portfolio = p2
        assert portfolio_manager.portfolio is p2

        with session_manager(actor="tester", reason="ordering-commit"):
            seq = ledg.journal.transactions
            # Initial ordering should be by date: t1, t2, t3
            assert list(seq) == [t1, t2, t3]
            # Removing and re-adding should preserve date ordering
            seq.discard(t2)
            assert list(seq) == [t1, t3]
            seq.add(t2)
            assert list(seq) == [t1, t2, t3]

        p3 = p2.superseding
        assert p3 is not None
        new_ledger = p3[ledg.uid]
        assert list(new_ledger.transactions) == [t1, t2, t3]

