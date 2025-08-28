# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest
from iso4217 import Currency

from app.portfolio.portfolio import Portfolio
from app.portfolio.models.instrument import Instrument
from app.portfolio.models.ledger import Ledger
from app.util.helpers.frozendict import frozendict

import pydantic


@pytest.mark.portfolio
class TestPortfolio:
    def test_basic_initialization_and_audit(self):
        p = Portfolio()
        assert p.uid.namespace == "Portfolio"
        assert p.uid.id == 1
        assert p.version == 1
        assert p.entity_log.entity_uid == p.uid
        assert len(p.entity_log) == 1
        assert p.entity_log.exists is True
        assert p.entity_log.next_version == 2
        assert p.ledgers == {}

    def test_session_manager_cached_property(self):
        p = Portfolio()
        sm1 = p.session_manager
        sm2 = p.session_manager
        assert sm1 is sm2  # cached_property

    def test_add_ledger_by_reconstruction(self):
        # Portfolio currently immutable; simulate adding ledger by cloning via update
        p1 = Portfolio()
        inst = Instrument(
            ticker="AAPL",
            currency=Currency("USD"),
        )
        ledg = Ledger(instrument=inst)

        p2 = p1.update(ledgers=frozendict({inst.uid: ledg}))

        assert p2 is not p1
        assert p1.superseded
        assert not p2.superseded
        assert p2.version == 2
        assert p2.ledgers[inst.uid] is ledg
