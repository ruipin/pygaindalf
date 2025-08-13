# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime
from decimal import Decimal
import re

from typing import Generator

import pytest

from app.components.providers.forex.oanda import OandaForexProviderConfig, OandaForexProvider
from app.config import CFG


@pytest.fixture(scope='function')
def oanda_provider() -> Generator[OandaForexProvider]:
    # Minimal config enabling the Oanda forex provider
    cfg = OandaForexProviderConfig.model_validate({
        'package': 'forex.oanda'
    })

    # Build provider instance using resolved component class
    yield OandaForexProvider(cfg)


@pytest.mark.components
@pytest.mark.providers
@pytest.mark.forex
@pytest.mark.forex_oanda
class TestOandaForexProvider:
    def _oanda_pattern(self):
        return re.compile(r'^https://fxds-public-exchange-rates-api\.oanda\.com/cc-api/currencies(\?.*)?$')

    def test_get_daily_rate_parses_average_bid(self, oanda_provider, requests_mock):
        requests_mock.get(
            self._oanda_pattern(),
            json={
                'response': [
                    {
                        'average_bid': '0.859510',
                        'base_currency': 'USD',
                        'quote_currency': 'EUR',
                        'close_time': '2025-08-11T23:59:59Z',
                    }
                ]
            },
            status_code=200,
        )

        test_date = datetime.date(2025, 8, 12)
        rate = oanda_provider.get_daily_rate('usd', 'eur', test_date)
        assert isinstance(rate, Decimal)
        assert rate == Decimal('0.859510')
        assert len(requests_mock.request_history) == 1

    def test_convert_currency_uses_rate(self, oanda_provider, requests_mock):
        requests_mock.get(
            self._oanda_pattern(),
            json={'response': [{'average_bid': '2.5'}]},
            status_code=200,
        )

        test_date = datetime.date(2025, 8, 12)
        amount = Decimal('100')

        converted = oanda_provider.convert_currency(amount, 'USD', 'EUR', test_date)
        assert isinstance(converted, Decimal)
        assert converted == Decimal('250')

    def test_error_on_invalid_response(self, oanda_provider, requests_mock):
        requests_mock.get(
            self._oanda_pattern(),
            json={'invalid': []},
            status_code=200,
        )

        with pytest.raises(ValueError):
            oanda_provider.get_daily_rate('USD', 'EUR', datetime.date(2025, 8, 12))

    def test_error_on_http_failure(self, oanda_provider, requests_mock):
        requests_mock.get(
            self._oanda_pattern(),
            text='Server error',
            status_code=500,
        )

        with pytest.raises(ValueError):
            oanda_provider.get_daily_rate('USD', 'EUR', datetime.date(2025, 8, 12))

    def test_memoization_caches_results(self, oanda_provider, requests_mock):
        requests_mock.get(
            self._oanda_pattern(),
            json={'response': [{'average_bid': '1.2345'}]},
            status_code=200,
        )

        d = datetime.date(2025, 8, 12)
        r1 = oanda_provider.get_daily_rate('USD', 'EUR', d)
        r2 = oanda_provider.get_daily_rate('USD', 'EUR', d)
        assert r1 == r2 == Decimal('1.2345')
        assert len(requests_mock.request_history) == 1  # second call should hit lru_cache
