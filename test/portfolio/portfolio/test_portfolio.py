# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest
from iso4217 import Currency

from app.portfolio.models.root.portfolio_root import PortfolioRoot
from app.portfolio.models.portfolio import Portfolio
from app.portfolio.models.instrument.instrument import Instrument
from app.portfolio.models.ledger.ledger import Ledger
from app.util.helpers.frozendict import frozendict

import pydantic


@pytest.mark.portfolio
class TestPortfolio:
    def test_basic_initialization_and_audit(self, portfolio_root):
        p = portfolio_root.portfolio
        assert p.uid.namespace == "Portfolio"
        assert p.uid.id == 1
        assert p.version == 1
        assert p.entity_log.entity_uid == p.uid
        assert len(p.entity_log) == 1
        assert p.entity_log.exists is True
        assert p.entity_log.next_version == 2
        assert p.ledgers == set()
        assert len(p.ledgers) == 0
