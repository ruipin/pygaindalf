# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest

from iso4217 import Currency

from app.portfolio.models.instrument.instrument import Instrument
from app.portfolio.models.instrument.instrument_proxy import InstrumentProxy


@pytest.mark.portfolio
@pytest.mark.instrument
@pytest.mark.proxy
class TestInstrumentProxy:
    def test_proxy_reuses_existing_instance_from_entity(self):
        instrument = Instrument(
            ticker="AAPL",
            currency=Currency("USD"),
        )

        proxy_from_entity = instrument.proxy
        proxy_from_constructor = InstrumentProxy(instrument)

        assert proxy_from_constructor is proxy_from_entity

    def test_proxy_construction_from_uid_returns_existing_proxy(self):
        instrument = Instrument(
            ticker="MSFT",
            currency=Currency("USD"),
        )

        proxy_from_uid = InstrumentProxy(instrument.uid)

        assert proxy_from_uid is instrument.proxy

    def test_proxy_forwards_attribute_access_and_uid(self):
        instrument = Instrument(
            ticker="NVDA",
            currency=Currency("USD"),
        )

        proxy = instrument.proxy

        assert proxy.entity is instrument
        assert proxy.uid is instrument.uid
        assert proxy.ticker == instrument.ticker
        assert proxy.currency == instrument.currency

    def test_proxy_tracks_superseding_entity_versions(self):
        instrument = Instrument(
            ticker="GOOG",
            currency=Currency("USD"),
        )

        proxy = instrument.proxy
        assert proxy.entity is instrument

        updated = instrument.update(currency=Currency("GBP"))

        # First access ensures the proxy refreshes its cached weakref
        assert proxy.entity is updated
        assert proxy.currency == Currency("GBP")
