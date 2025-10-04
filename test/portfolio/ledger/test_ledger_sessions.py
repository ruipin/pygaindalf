# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""Session-backed tests validating propagation of child sort-key changes from Transaction -> Ledger via the JournalledOrderedViewSet mechanism.

These mirror the requested behavior: when a Transaction entity's sort key (date) changes
inside a session, the parent Ledger journal should record an ITEM_UPDATED edit for that
transaction UID, but only if the transaction is currently tracked in the set.

We set up a minimal root that exposes a SessionManager so the Ledger entity participates in
the session-managed hierarchy.
"""

import datetime

from decimal import Decimal

import pytest

from iso4217 import Currency

from app.portfolio.collections.journalled.set import JournalledSetEdit, JournalledSetEditType
from app.portfolio.journal.session import Session
from app.portfolio.journal.session_manager import SessionManager
from app.portfolio.models.instrument import Instrument
from app.portfolio.models.ledger import Ledger
from app.portfolio.models.root import EntityRoot
from app.portfolio.models.transaction import Transaction, TransactionType


# --- Tests -----------------------------------------------------------------------
@pytest.mark.portfolio
@pytest.mark.ledger
@pytest.mark.session
class TestLedgerJournalPropagationSessions:
    def test_child_sort_key_change_populates_parent_diff(self, entity_root: EntityRoot, session_manager: SessionManager):
        with session_manager(actor="tester", reason="test_child_sort_key_change_populates_parent_diff") as s:
            inst = Instrument(ticker="AMD", currency=Currency("USD"))
            # Seed ledger with two transactions ordered by date
            t1 = Transaction(
                type=TransactionType.BUY,
                date=datetime.date(2025, 1, 1),
                quantity=Decimal(1),
                consideration=Decimal(1),
            )
            t2 = Transaction(
                type=TransactionType.BUY,
                date=datetime.date(2025, 1, 3),
                quantity=Decimal(2),
                consideration=Decimal(2),
            )
            ledg = Ledger(instrument=inst, transactions={t1, t2})

            # Attach ledger under owner so it participates in the session-managed hierarchy
            entity_root.root = ledg

        # Check hierarchy
        assert ledg is t1.instance_parent
        assert ledg is t2.instance_parent
        assert entity_root is ledg.instance_parent

        # Modify t1 date inside a session
        with session_manager(actor="tester", reason="tx-date-change") as s:
            assert isinstance(s, Session)

            # Parent journal initially has no diff
            lj = ledg.journal
            assert lj.get_diff() == {}

            # Change child sort key (Transaction.sort_key uses date)
            tj = t1.journal
            tj.date = datetime.date(2025, 1, 5)

        # After invalidation propagation, parent should have an ITEM_UPDATED edit for t1
        diff = lj.get_diff()
        assert "transactions" in diff
        journal = diff["transactions"]
        assert isinstance(journal, tuple) and len(journal) == 1
        edit = journal[0]
        assert edit.type is JournalledSetEditType.ITEM_UPDATED
        assert edit.value == t1.uid

    def test_no_parent_diff_when_sort_key_unchanged(self, entity_root: EntityRoot, session_manager: SessionManager):
        with session_manager(actor="tester", reason="test_no_parent_diff_when_sort_key_unchanged") as s:
            inst = Instrument(ticker="MSFT", currency=Currency("USD"))
            t1 = Transaction(
                type=TransactionType.BUY,
                date=datetime.date(2025, 2, 1),
                quantity=Decimal(1),
                consideration=Decimal(1),
            )
            t2 = Transaction(
                type=TransactionType.BUY,
                date=datetime.date(2025, 2, 2),
                quantity=Decimal(2),
                consideration=Decimal(2),
            )
            ledg = Ledger(instrument=inst, transactions={t1, t2})
            entity_root.root = ledg

        with session_manager(actor="tester", reason="no-op-date") as s:
            lj = ledg.journal
            assert lj.get_diff() == {}

            tj = t1.journal
            # Change a field that does NOT affect sort key (fees)
            tj.fees = Decimal(999)

            # No diff since sort key didn't change
            assert lj.get_diff() == {}
            s.abort()

    def test_no_parent_diff_when_child_not_in_parent_set(self, entity_root: EntityRoot, session_manager: SessionManager):
        with session_manager(actor="tester", reason="test_no_parent_diff_when_child_not_in_parent_set") as s:
            inst = Instrument(ticker="GOOGL", currency=Currency("USD"))
            # Two independent transactions
            t1 = Transaction(
                type=TransactionType.BUY,
                date=datetime.date(2025, 3, 1),
                quantity=Decimal(1),
                consideration=Decimal(1),
            )
            t2 = Transaction(
                type=TransactionType.BUY,
                date=datetime.date(2025, 3, 2),
                quantity=Decimal(1),
                consideration=Decimal(1),
            )
            ledg = Ledger(instrument=inst, transactions={t1, t2})
            entity_root.root = ledg

        with session_manager(actor="tester", reason="not-member") as s:
            lj = ledg.journal
            assert lj.get_diff() == {}

            # Remove t1 from the ledger set
            ledg.journal.transactions.discard(t1)

            # Modify t1 (not present in ledger set) sort key
            tj = t1.journal
            tj.date = datetime.date(2025, 3, 5)

            # Still no diff because child isn't in the parent's OrderedViewMutableSet
            assert lj.get_diff() == {"transactions": (JournalledSetEdit(type=JournalledSetEditType.DISCARD, value=t1.uid),)}
            s.abort()
