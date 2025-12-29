# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime

from decimal import Decimal

import pytest

from app.portfolio.models.entity.entity_log import EntityLog, EntityModificationType
from app.portfolio.models.instrument import Instrument
from app.portfolio.models.instrument.instrument_type import InstrumentType
from app.portfolio.models.ledger import Ledger
from app.portfolio.models.transaction import Transaction, TransactionType
from app.util.helpers.currency import Currency
from app.util.helpers.decimal_currency import DecimalCurrency


@pytest.mark.portfolio
@pytest.mark.ledger
class TestLedgerEntity:
    def test_entity_initialization_sets_instance_name_and_audit(self):
        instrument = Instrument(
            ticker="AAPL",
            type=InstrumentType.EQUITY,
            currency=Currency("USD"),
        )
        ledger = Ledger(instrument=instrument)

        record = ledger.record
        assert ledger.instance_name == f"Ledger@{instrument.instance_name}"
        assert ledger.uid.namespace == "Ledger"
        assert record.version == 1
        assert record.entity_log.entity_uid == ledger.uid
        assert len(record.entity_log) == 1
        assert record.entity_log.exists is True
        assert record.entity_log.next_version == 2

    def test_entity_reuses_instance_per_instrument(self):
        instrument = Instrument(
            ticker="MSFT",
            type=InstrumentType.EQUITY,
            currency=Currency("USD"),
        )

        ledger1 = Ledger(instrument=instrument)
        ledger2 = Ledger(instrument=instrument)

        assert ledger1 is ledger2
        assert Ledger.by_instrument(instrument) is ledger1

    def test_entity_wraps_record_and_exposes_transactions(self):
        instrument = Instrument(
            ticker="AAPL",
            type=InstrumentType.EQUITY,
            currency=Currency("USD"),
        )
        txn = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 1, 1),
            quantity=Decimal(1),
            consideration=DecimalCurrency(100, currency="USD"),
        )

        ledger = Ledger(
            instrument=instrument,
            transactions={txn},
        )

        assert ledger.instrument is instrument
        assert ledger.record.instrument is instrument
        assert len(ledger) == 1
        assert list(ledger.transactions) == [txn]
        assert Ledger.by_uid(ledger.uid) is ledger

    def test_entity_accepts_iterable_transaction_input(self):
        instrument = Instrument(
            ticker="NFLX",
            type=InstrumentType.EQUITY,
            currency=Currency("USD"),
        )
        t1 = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 4, 1),
            quantity=Decimal(1),
            consideration=DecimalCurrency(500, currency="USD"),
        )
        t2 = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 4, 2),
            quantity=Decimal(2),
            consideration=DecimalCurrency(1000, currency="USD"),
        )

        ledger = Ledger(instrument=instrument, transactions=(t1, t2))

        assert len(ledger.transactions) == 2
        assert list(ledger.transactions) == [t1, t2]

    def test_entity_refreshes_after_superseding_record(self):
        instrument = Instrument(
            ticker="MSFT",
            type=InstrumentType.EQUITY,
            currency=Currency("USD"),
        )
        txn1 = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 2, 1),
            quantity=Decimal(2),
            consideration=DecimalCurrency(200, currency="USD"),
        )
        ledger = Ledger(
            instrument=instrument,
            transactions={txn1},
        )

        original_record = ledger.record

        txn2 = Transaction(
            type=TransactionType.SELL,
            date=datetime.date(2025, 2, 3),
            quantity=Decimal(1),
            consideration=DecimalCurrency(150, currency="USD"),
        )
        ledger.update(transactions={txn1, txn2})

        updated_record = ledger.record
        assert updated_record is not original_record
        assert original_record.superseded
        assert updated_record is original_record.superseding
        assert list(ledger.transactions) == [txn1, txn2]
        assert Ledger.by_uid(ledger.uid) is ledger

        log = ledger.record.entity_log
        assert log.version == 2
        entry_v1 = log.get_entry_by_version(1)
        assert entry_v1 is not None and entry_v1.what == EntityModificationType.CREATED
        if EntityLog.TRACK_ENTITY_DIFF:
            assert entry_v1.diff == {"instrument": instrument, "transactions": {txn1}}

        entry_v2 = log.get_entry_by_version(2)
        assert entry_v2 is not None and entry_v2.what == EntityModificationType.UPDATED
