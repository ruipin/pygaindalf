# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest
from iso4217 import Currency

from app.portfolio.manager import PortfolioManager
from app.portfolio.models.portfolio import Portfolio
from app.portfolio.models.instrument import Instrument
from app.portfolio.models.ledger.ledger import Ledger
from app.util.helpers.frozendict import frozendict

import pydantic


@pytest.fixture
def portfolio_manager() -> PortfolioManager:
    return PortfolioManager()

@pytest.fixture
def portfolio(portfolio_manager : PortfolioManager) -> Portfolio:
    return portfolio_manager.portfolio


@pytest.mark.portfolio
class TestPortfolio:
    def test_basic_initialization_and_audit(self, portfolio : Portfolio):
        p = portfolio
        assert p.uid.namespace == "Portfolio"
        assert p.uid.id == 1
        assert p.version == 1
        assert p.entity_log.entity_uid == p.uid
        assert len(p.entity_log) == 1
        assert p.entity_log.exists is True
        assert p.entity_log.next_version == 2
        assert p.ledgers == set()

    def test_session_manager_cached_property(self, portfolio_manager : PortfolioManager, portfolio : Portfolio):
        p = portfolio
        sm1 = p.session_manager
        sm2 = p.session_manager
        assert sm1 is sm2  # cached_property
        assert sm1 is portfolio_manager.session_manager

    def test_add_ledger_by_reconstruction(self, portfolio : Portfolio):
        # Portfolio currently immutable; simulate adding ledger by cloning via update
        p1 = portfolio
        inst = Instrument(
            ticker="AAPL",
            currency=Currency("USD"),
        )
        ledg = Ledger(instrument_uid=inst.uid)

        p2 = p1.update(ledger_uids={ledg.uid})

        assert p2 is not p1
        assert p1.superseded
        assert not p2.superseded
        assert p2.version == 2
        assert ledg in p2
