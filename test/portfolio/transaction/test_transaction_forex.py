# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime

from decimal import Decimal

import pytest

from iso4217 import Currency

from app.portfolio.models.annotation.forex.forex_annotation import ForexAnnotation
from app.portfolio.models.instrument import Instrument
from app.portfolio.models.instrument.instrument_type import InstrumentType
from app.portfolio.models.transaction import Transaction, TransactionType
from app.util.helpers.decimal_currency import DecimalCurrency


@pytest.mark.portfolio
@pytest.mark.transaction
class TestTransactionForexAnnotation:
    def test_forex_annotation_manual(self):
        inst = Instrument(ticker="AAPL", type=InstrumentType.EQUITY, currency=Currency("USD"))
        txn = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 1, 1),
            quantity=Decimal(10),
            consideration=DecimalCurrency(1500, currency="USD"),
        )
        from app.portfolio.models.ledger import Ledger

        _ledger = Ledger(instrument=inst, transactions={txn})

        _annotation = ForexAnnotation.create(
            txn,
            exchange_rates={Currency("EUR"): Decimal(11), Currency("JPY"): Decimal(150)},
            considerations={Currency("EUR"): DecimalCurrency("1650 EUR"), Currency("JPY"): DecimalCurrency("225000 JPY")},
        )

        assert txn.get_consideration(currency=Currency("EUR")) == Decimal(1650)
        assert txn.get_consideration(currency=Currency("JPY")) == Decimal(225000)

    def test_forex_annotation_fallback_to_provider(self):
        inst = Instrument(ticker="AAPL", type=InstrumentType.EQUITY, currency=Currency("USD"))
        txn = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 1, 1),
            quantity=Decimal(10),
            consideration=DecimalCurrency(1500, currency="USD"),
        )
        from app.portfolio.models.ledger import Ledger

        _ledger = Ledger(instrument=inst, transactions={txn})

        with pytest.raises(RuntimeError, match="No active context found"):
            txn.get_consideration(currency=Currency("GBP"))
