# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime
import pytest
from decimal import Decimal

from iso4217 import Currency

from app.portfolio.models.instrument import Instrument
from app.portfolio.models.ledger.ledger import Ledger
from app.portfolio.models.transaction.transaction import Transaction, TransactionType


@pytest.mark.portfolio
@pytest.mark.ledger
class TestLedger:
    def test_initialization_uses_instrument_name_and_audit(self):
        inst = Instrument.model_validate({
            "ticker": "MSFT",
            "currency": Currency("USD"),
        })
        ledg = Ledger.model_validate({
            "instrument_uid": inst.uid,
        })

        # Name and linkage
        assert ledg.instance_name == f'Ledger@{inst.instance_name}'
        assert ledg.instrument is inst

        # Instance store lookup
        by_name = Ledger.by_instrument(inst)
        assert by_name is ledg

        # Audit basics
        assert ledg.version == 1
        assert ledg.entity_log.entity_uid == ledg.uid
        assert len(ledg.entity_log) == 1
        assert ledg.entity_log.exists is True
        assert ledg.entity_log.next_version == 2

    def test_ledger_with_transactions_set_interface(self):
        inst = Instrument(
            ticker="AAPL",
            currency=Currency("USD"),
        )
        # Manually construct transactions (ledger currently immutable, so we just build iterable)
        tx1 = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 1, 1),
            quantity=Decimal("10"),
            consideration=Decimal("1500"),
        )
        tx2 = Transaction(
            type=TransactionType.SELL,
            date=datetime.date(2025, 1, 5),
            quantity=Decimal("4"),
            consideration=Decimal("620"),
        )

        ledg = Ledger(
            instrument_uid=inst.uid,
            # Provide a set (primary expected input type now)
            transaction_uids={tx1.uid, tx2.uid},
        )

        assert len(ledg) == 2
        assert ledg.length == 2
        # OrderedViewSet sorts by transaction date; tx1 earlier than tx2
        assert ledg[0] is tx1
        assert ledg[1] is tx2
        assert list(iter(ledg)) == [tx1, tx2]

    def test_ledger_with_transactions_iterable_sequence_input(self):
        """Validate that non-set iterables (e.g. sequence/tuple) are accepted and coerced."""
        inst = Instrument(
            ticker="NFLX",
            currency=Currency("USD"),
        )
        tx1 = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 4, 1),
            quantity=Decimal("1"),
            consideration=Decimal("500"),
        )
        tx2 = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 4, 2),
            quantity=Decimal("2"),
            consideration=Decimal("1000"),
        )
        # Supply a tuple (sequence) to test broader Iterable support
        ledg = Ledger(
            instrument_uid=inst.uid,
            transaction_uids=(tx1.uid, tx2.uid),
        )
        assert len(ledg) == 2
        assert ledg[0] is tx1 and ledg[1] is tx2

    def test_ledger_uid_and_instance_name_stable(self):
        inst = Instrument(
            ticker="TSLA",
            currency=Currency("USD"),
        )
        ledg1 = Ledger(instrument_uid=inst.uid)
        # Reinitialize with same instrument (should reuse)
        ledg2 = Ledger(instrument_uid=inst.uid)

        assert ledg1 is ledg2