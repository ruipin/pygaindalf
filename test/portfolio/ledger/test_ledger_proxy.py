# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime

from decimal import Decimal

import pytest

from iso4217 import Currency

from app.portfolio.models.instrument.instrument import Instrument
from app.portfolio.models.instrument.instrument_proxy import InstrumentProxy
from app.portfolio.models.ledger.ledger import Ledger
from app.portfolio.models.ledger.ledger_proxy import LedgerProxy
from app.portfolio.models.transaction import Transaction, TransactionType
from app.portfolio.models.transaction.transaction_proxy import TransactionProxy


@pytest.mark.portfolio
@pytest.mark.ledger
@pytest.mark.proxy
class TestLedgerProxy:
    def test_proxy_reuses_existing_instance_from_entity(self):
        instrument = Instrument(
            ticker="AAPL",
            currency=Currency("USD"),
        )
        ledger = Ledger(instrument_uid=instrument.uid)

        proxy_from_entity = ledger.proxy
        proxy_from_constructor = LedgerProxy(ledger)

        assert proxy_from_constructor is proxy_from_entity

    def test_proxy_construction_from_uid_returns_existing_proxy(self):
        instrument = Instrument(
            ticker="MSFT",
            currency=Currency("USD"),
        )
        ledger = Ledger(instrument_uid=instrument.uid)

        proxy_from_uid = LedgerProxy(ledger.uid)

        assert proxy_from_uid is ledger.proxy

    def test_proxy_forwards_basic_attributes(self):
        instrument = Instrument(
            ticker="NVDA",
            currency=Currency("USD"),
        )
        ledger = Ledger(instrument_uid=instrument.uid)

        proxy = ledger.proxy

        assert proxy.entity is ledger
        assert proxy.uid is ledger.uid
        assert proxy.instrument_uid == ledger.instrument_uid

    def test_proxy_wraps_entity_attributes_into_proxies(self):
        instrument = Instrument(
            ticker="TSLA",
            currency=Currency("USD"),
        )
        ledger = Ledger(instrument_uid=instrument.uid)

        proxy = ledger.proxy
        instrument_from_proxy = proxy.instrument

        assert isinstance(instrument_from_proxy, InstrumentProxy)
        assert instrument_from_proxy.entity is instrument
        assert instrument_from_proxy.uid == instrument.uid

    def test_proxy_wraps_callable_results_into_proxies(self):
        instrument = Instrument(
            ticker="AMD",
            currency=Currency("USD"),
        )
        transaction = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 6, 1),
            quantity=Decimal(7),
            consideration=Decimal(910),
        )

        ledger = Ledger(
            instrument_uid=instrument.uid,
            transaction_uids={transaction.uid},
        )

        proxy = ledger.proxy

        result = proxy.__getitem__(0)

        assert isinstance(result, TransactionProxy)
        assert result.entity is transaction
        assert result.uid == transaction.uid

    def test_proxy_preserves_set_interface_behavior(self):
        instrument = Instrument(
            ticker="INTC",
            currency=Currency("USD"),
        )
        tx1 = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 7, 1),
            quantity=Decimal(15),
            consideration=Decimal(825),
        )
        tx2 = Transaction(
            type=TransactionType.SELL,
            date=datetime.date(2025, 7, 2),
            quantity=Decimal(5),
            consideration=Decimal(320),
        )

        ledger = Ledger(
            instrument_uid=instrument.uid,
            transaction_uids={tx1.uid, tx2.uid},
        )
        proxy = ledger.proxy

        assert tx1 in ledger
        assert tx1 in proxy
        assert tx1.uid in ledger.transaction_uids

        tx1_proxy = tx1.proxy
        tx2_proxy = tx2.proxy

        assert tx1_proxy in proxy
        assert tx2_proxy in proxy
        assert len(proxy) == len(ledger) == 2
        assert proxy.length == ledger.length == 2

        assert proxy[0].uid == tx1.uid
        assert proxy[1].uid == tx2.uid

        iterated = list(proxy)
        assert all(isinstance(item, TransactionProxy) for item in iterated)
        assert {item.uid for item in iterated} == {tx1.uid, tx2.uid}

    def test_proxy_set_membership_with_uids(self):
        instrument = Instrument(
            ticker="IBM",
            currency=Currency("USD"),
        )
        tx = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 8, 1),
            quantity=Decimal(3),
            consideration=Decimal(105),
        )

        ledger = Ledger(
            instrument_uid=instrument.uid,
            transaction_uids={tx.uid},
        )
        proxy = ledger.proxy

        assert tx.uid in ledger.transaction_uids
        assert tx in proxy
        assert tx.proxy in proxy

    def test_transactions_collection_returns_transaction_proxies(self):
        instrument = Instrument(
            ticker="GOOG",
            currency=Currency("USD"),
        )

        tx1 = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 4, 1),
            quantity=Decimal(10),
            consideration=Decimal(1500),
        )
        tx2 = Transaction(
            type=TransactionType.SELL,
            date=datetime.date(2025, 4, 2),
            quantity=Decimal(5),
            consideration=Decimal(800),
        )

        ledger = Ledger(
            instrument_uid=instrument.uid,
            transaction_uids={tx1.uid, tx2.uid},
        )
        proxy = ledger.proxy

        transactions = list(proxy.transactions)

        assert len(transactions) == 2
        assert all(isinstance(tx, TransactionProxy) for tx in transactions)
        assert {tx.uid for tx in transactions} == {tx1.uid, tx2.uid}
