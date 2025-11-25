# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest

from iso4217 import Currency

from app.portfolio.models.instrument import Instrument
from app.portfolio.models.instrument.instrument_type import InstrumentType
from app.portfolio.models.ledger import Ledger
from app.portfolio.models.portfolio import Portfolio


@pytest.mark.portfolio
class TestPortfolioEntity:
    def test_entity_initialization_creates_record(self):
        portfolio = Portfolio()
        record = portfolio.record

        assert portfolio.record is record
        assert portfolio.uid == record.uid
        assert portfolio.uid.namespace == "Portfolio"
        assert len(portfolio.ledgers) == 0
        assert list(portfolio) == []
        assert Portfolio.by_uid(portfolio.uid) is portfolio

    def test_entity_refreshes_after_update(self):
        portfolio = Portfolio()
        initial_record = portfolio.record

        inst = Instrument(ticker="AAPL", type=InstrumentType.EQUITY, currency=Currency("USD"))
        ledger = Ledger(instrument=inst)

        portfolio.update(ledgers={ledger})

        superseding_record = portfolio.record
        assert superseding_record is not initial_record
        assert superseding_record is initial_record.superseding
        assert ledger in portfolio.ledgers
        assert ledger in portfolio
        assert Portfolio.by_uid(portfolio.uid) is portfolio
