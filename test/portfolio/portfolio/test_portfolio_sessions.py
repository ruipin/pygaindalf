# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""Tests exercising portfolio session code paths via PortfolioRoot.

These tests intentionally avoid using any bespoke session fixtures and instead
drive everything through a real `PortfolioRoot` and its `session_manager`.

They validate ledger + transaction add/remove and reordering behaviors using
the journalling layer (JournalledMapping / JournalledSequence) across commits
and aborts.
"""

import datetime

from collections.abc import MutableSet
from collections.abc import Set as AbstractSet
from decimal import Decimal

import pytest

from app.portfolio.collections.journalled.mapping import JournalledMapping  # noqa: F401 (documentation/reference)
from app.portfolio.collections.journalled.sequence import JournalledSequence  # noqa: F401 (documentation/reference)
from app.portfolio.models.instrument import Instrument
from app.portfolio.models.instrument.instrument_type import InstrumentType
from app.portfolio.models.ledger import Ledger
from app.portfolio.models.portfolio import Portfolio
from app.portfolio.models.root.portfolio_root import PortfolioRoot
from app.portfolio.models.transaction import Transaction, TransactionType
from app.util.helpers.currency import Currency
from app.util.helpers.decimal_currency import DecimalCurrency


@pytest.mark.portfolio
@pytest.mark.session
class TestPortfolioSessions:
    def test_add_ledgers_commit(self, portfolio_root: PortfolioRoot, session_manager):
        portfolio = portfolio_root.portfolio
        initial_record = portfolio.record
        assert len(portfolio.ledgers) == 0
        assert list(portfolio) == []
        assert Portfolio(uid=initial_record.uid) is portfolio

        with session_manager(actor="tester", reason="test_add_ledgers_commit") as s:
            inst1 = Instrument(ticker="AAPL", type=InstrumentType.EQUITY, currency=Currency("USD"))
            ledg1 = Ledger(instrument=inst1)

            inst2 = Instrument(ticker="MSFT", type=InstrumentType.EQUITY, currency=Currency("USD"))
            ledg2 = Ledger(instrument=inst2)

            from app.portfolio.models.portfolio.portfolio_journal import PortfolioJournal

            journal = portfolio.journal
            assert type(journal) is PortfolioJournal
            ledgers_set = journal.ledgers
            ledgers_set.add(ledg1)
            ledgers_set.add(ledg2)
            assert portfolio.record.dirty is True
            assert s.dirty is True

        # Session auto-commits on exit -> portfolio superseded
        updated_record = portfolio.record
        assert updated_record is not None and updated_record is not initial_record
        assert updated_record is initial_record.superseding
        assert updated_record is portfolio_root.portfolio.record
        # Membership only; set holds ledger entities
        assert ledg1 in portfolio.ledgers and ledg2 in portfolio.ledgers
        # Retrieve via portfolio __getitem__ using Instrument instances
        assert portfolio[inst1] is ledg1
        assert portfolio[inst2] is ledg2

    def test_add_and_remove_ledger_abort(self, portfolio_root: PortfolioRoot, session_manager):
        portfolio = Portfolio(uid=portfolio_root.portfolio.uid)
        initial_record = portfolio.record

        with session_manager(actor="tester", reason="setup-ledger") as s:
            inst = Instrument(ticker="GOOGL", type=InstrumentType.EQUITY, currency=Currency("USD"))
            ledger = Ledger(instrument=inst)

            ledgers_set = portfolio.journal.ledgers
            ledgers_set.add(ledger)
            assert ledger in ledgers_set
            assert portfolio.record.dirty

            s.abort()  # abort edits
            assert not s.dirty
            assert ledger not in portfolio.ledgers

        assert portfolio.record is initial_record
        assert ledger not in portfolio.ledgers

    def test_remove_existing_ledger_commit(self, portfolio_root: PortfolioRoot, session_manager):
        portfolio = Portfolio(uid=portfolio_root.portfolio.uid)
        initial_record = portfolio.record

        with session_manager(actor="tester", reason="setup-ledger"):
            inst = Instrument(ticker="ORCL", type=InstrumentType.EQUITY, currency=Currency("USD"))
            ledger = Ledger(instrument=inst)
            portfolio.journal.ledgers.add(ledger)
            ledger_uid = ledger.uid

        ledger = Ledger.by_uid(ledger_uid)
        second_record = portfolio.record
        assert second_record is not initial_record
        assert second_record is initial_record.superseding
        assert ledger in portfolio.ledgers

        with session_manager(actor="tester", reason="remove-ledger"):
            portfolio.journal.ledgers.discard(ledger)

        final_record = portfolio.record
        assert final_record is not second_record
        assert final_record is second_record.superseding
        assert ledger.deleted is True
        assert ledger.record_or_none is None
        assert ledger not in portfolio.ledgers

    def test_add_transactions_commit_and_ordering(self, portfolio_root: PortfolioRoot, session_manager):
        portfolio = Portfolio(uid=portfolio_root.portfolio.uid)
        with session_manager(actor="tester", reason="setup-ledger"):
            inst = Instrument(ticker="TSLA", type=InstrumentType.EQUITY, currency=Currency("USD"))
            ledger = Ledger(instrument=inst)
            portfolio.journal.ledgers.add(ledger)
            ledger_uid = ledger.uid

        ledger = Ledger.by_uid(ledger_uid)
        second_record = portfolio.record

        with session_manager(actor="tester", reason="tx-add-reorder") as s:
            t1 = Transaction(
                type=TransactionType.BUY,
                date=datetime.date(2025, 1, 1),
                quantity=Decimal(10),
                consideration=DecimalCurrency(1000, currency="USD"),
            )
            t2 = Transaction(
                type=TransactionType.SELL,
                date=datetime.date(2025, 1, 2),
                quantity=Decimal(4),
                consideration=DecimalCurrency(420, currency="USD"),
            )
            t3 = Transaction(
                type=TransactionType.BUY,
                date=datetime.date(2025, 1, 3),
                quantity=Decimal(6),
                consideration=DecimalCurrency(630, currency="USD"),
            )

            assert isinstance(ledger.transactions, AbstractSet) and not isinstance(ledger.transactions, MutableSet)
            tx_set = ledger.journal.transactions
            assert len(tx_set) == 0

            tx_set.add(t2)
            tx_set.add(t3)
            tx_set.add(t1)

            assert len(tx_set) == 3
            assert list(tx_set) == [t1, t2, t3]
            assert s.dirty and ledger.record.dirty and portfolio.record.dirty

        third_record = portfolio.record
        assert third_record is not None
        assert third_record is not second_record
        assert third_record is second_record.superseding
        assert third_record is portfolio_root.portfolio.record

        ledger = Ledger.by_uid(ledger_uid)
        assert list(ledger.transactions) == [t1, t2, t3]

    def test_remove_transaction_abort(self, portfolio_root: PortfolioRoot, session_manager):
        portfolio = Portfolio(uid=portfolio_root.portfolio.uid)
        with session_manager(actor="tester", reason="setup-ledger"):
            inst = Instrument(ticker="NVDA", type=InstrumentType.EQUITY, currency=Currency("USD"))
            t1 = Transaction(
                type=TransactionType.BUY,
                date=datetime.date(2025, 2, 1),
                quantity=Decimal(5),
                consideration=DecimalCurrency(2500, currency="USD"),
            )
            t2 = Transaction(
                type=TransactionType.BUY,
                date=datetime.date(2025, 2, 2),
                quantity=Decimal(3),
                consideration=DecimalCurrency(1500, currency="USD"),
            )
            ledger = Ledger(instrument=inst)
            portfolio.journal.ledgers.add(ledger)
            journal_tx = ledger.journal.transactions
            journal_tx.add(t1)
            journal_tx.add(t2)
            ledger_uid = ledger.uid

        ledger = Ledger.by_uid(ledger_uid)
        second_record = portfolio.record
        assert ledger in portfolio.ledgers
        assert list(second_record[ledger.uid].transactions) == [t1, t2]

        with session_manager(actor="tester", reason="tx-remove-abort") as s:
            tx_set = ledger.journal.transactions
            assert list(tx_set) == [t1, t2]
            tx_set.discard(t1)
            assert list(tx_set) == [t2]
            assert s.dirty
            s.abort()
            assert not s.dirty
            assert [tx.uid for tx in ledger.transactions] == [t1.uid, t2.uid]

        ledger = Ledger.by_uid(ledger_uid)
        assert list(second_record[ledger.uid].transactions) == [t1, t2]

    def test_attach_delete_then_recreate_unattached(self, portfolio_root: PortfolioRoot, session_manager):
        portfolio = portfolio_root.portfolio

        with session_manager(actor="tester", reason="attach-ledger"):
            inst = Instrument(ticker="IBM", type=InstrumentType.EQUITY, currency=Currency("USD"))
            ledger = Ledger(instrument=inst)
            portfolio.journal.ledgers.add(ledger)
            ledger_uid = ledger.uid

        ledger = Ledger.by_uid(ledger_uid)
        assert ledger in portfolio.ledgers
        assert ledger.exists is True
        assert ledger.deleted is False

        with session_manager(actor="tester", reason="delete-ledger"):
            portfolio.journal.ledgers.discard(ledger)

        assert ledger.deleted is True
        assert ledger.exists is False
        assert ledger.record_or_none is None
        assert Ledger.by_uid_or_none(ledger_uid) is ledger
        assert ledger not in portfolio.ledgers
        assert portfolio_root.entity_store.get_entity_record(ledger_uid) is None

        with session_manager(actor="tester", reason="create-unattached"):
            inst = Instrument(ticker="IBM", type=InstrumentType.EQUITY, currency=Currency("USD"))
            orphan = Ledger(instrument=inst)

            assert orphan.uid == ledger.uid

        assert orphan.instance_parent is None
        assert orphan.version == 2
        assert orphan.exists is False
        assert orphan.deleted is True

        orphan_record = orphan.record_or_none
        assert orphan_record is None
        assert Ledger.by_uid_or_none(ledger.uid) is ledger
        assert ledger.version == 2
        assert ledger.entity_log.version == 2

    def test_delete_then_commit_then_recreate_without_gc(self, portfolio_root: PortfolioRoot, session_manager):
        portfolio = portfolio_root.portfolio

        with session_manager(actor="tester", reason="attach-ledger for delete no gc"):
            inst = Instrument(ticker="CRM", type=InstrumentType.EQUITY, currency=Currency("USD"))
            ledger = Ledger(instrument=inst)
            portfolio.journal.ledgers.add(ledger)

        with session_manager(actor="tester", reason="delete-ledger no gc") as s:
            portfolio.journal.ledgers.discard(ledger)
            ledger.delete()

            assert s.dirty is True
            assert ledger.marked_for_deletion is True
        assert ledger.deleted is True
        assert ledger.exists is False

        with session_manager(actor="tester", reason="recreate-ledger no gc"):
            inst = Instrument(ticker="CRM", type=InstrumentType.EQUITY, currency=Currency("USD"))
            recreated = Ledger(instrument=inst)
            portfolio.journal.ledgers.add(recreated)

            assert recreated.exists is False

        assert recreated is ledger
        assert recreated.exists is True

    def test_delete_then_commit_then_recreate_with_gc(self, portfolio_root: PortfolioRoot, session_manager):
        import gc

        portfolio = portfolio_root.portfolio

        with session_manager(actor="tester", reason="attach-ledger for delete with gc"):
            inst = Instrument(ticker="ADBE", type=InstrumentType.EQUITY, currency=Currency("USD"))
            ledger = Ledger(instrument=inst)
            portfolio.journal.ledgers.add(ledger)

        with session_manager(actor="tester", reason="delete-ledger with gc") as s:
            portfolio.journal.ledgers.discard(ledger)
            ledger.delete()

            assert s.dirty is True
            assert ledger.marked_for_deletion is True
        assert ledger.deleted is True

        # Ensure no references remain
        ledger_uid = ledger.uid
        inst_uid = inst.uid
        del ledger
        del inst
        portfolio_root.entity_store.delete(ledger_uid, keep_log=False)
        portfolio_root.entity_store.delete(inst_uid, keep_log=False)
        gc.collect()
        assert portfolio_root.entity_store.get(ledger_uid, None) is None
        assert portfolio_root.entity_store.get(inst_uid, None) is None

        # Recreate
        with session_manager(actor="tester", reason="recreate-ledger with gc"):
            inst = Instrument(ticker="ADBE", type=InstrumentType.EQUITY, currency=Currency("USD"))
            recreated = Ledger(instrument=inst)
            portfolio.journal.ledgers.add(recreated)

        assert recreated.exists is True

    def test_reorder_transactions_commit(self, portfolio_root: PortfolioRoot, session_manager):
        portfolio = Portfolio(uid=portfolio_root.portfolio.uid)
        with session_manager(actor="tester", reason="setup-ledger"):
            inst = Instrument(ticker="IBM", type=InstrumentType.EQUITY, currency=Currency("USD"))
            t1 = Transaction(
                type=TransactionType.BUY,
                date=datetime.date(2025, 3, 1),
                quantity=Decimal(1),
                consideration=DecimalCurrency(100, currency="USD"),
            )
            t2 = Transaction(
                type=TransactionType.BUY,
                date=datetime.date(2025, 3, 2),
                quantity=Decimal(2),
                consideration=DecimalCurrency(210, currency="USD"),
            )
            t3 = Transaction(
                type=TransactionType.BUY,
                date=datetime.date(2025, 3, 3),
                quantity=Decimal(3),
                consideration=DecimalCurrency(330, currency="USD"),
            )
            ledger = Ledger(instrument=inst)
            portfolio.journal.ledgers.add(ledger)
            seq = ledger.journal.transactions
            seq.add(t1)
            seq.add(t2)
            seq.add(t3)
            ledger_uid = ledger.uid

        ledger = Ledger.by_uid(ledger_uid)

        with session_manager(actor="tester", reason="ordering-commit"):
            seq = ledger.journal.transactions
            assert list(seq) == [t1, t2, t3]
            seq.discard(t2)
            assert list(seq) == [t1, t3]
            seq.add(t2)
            assert list(seq) == [t1, t2, t3]

        updated_portfolio_record = portfolio.record
        new_ledger_record = updated_portfolio_record[ledger.uid]
        ledger = Ledger.by_uid(new_ledger_record.uid)
        assert list(ledger.transactions) == [t1, t2, t3]
