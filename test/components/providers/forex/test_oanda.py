# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime
import re

from decimal import Decimal

import pytest

from app.components.providers.forex.oanda import OandaForexProvider, OandaForexProviderConfig
from app.util.helpers.currency import Currency
from app.util.helpers.decimal import DecimalFactory
from app.util.helpers.decimal_currency import DecimalCurrency


@pytest.fixture
def oanda_provider() -> OandaForexProvider:
    # Minimal config enabling the Oanda forex provider
    cfg = OandaForexProviderConfig.model_validate({"package": "forex.oanda"})

    # Build provider instance using resolved component class
    provider = OandaForexProvider(cfg)

    # Inject Decimal factory for testing
    provider.__dict__["decimal"] = DecimalFactory()

    return provider


@pytest.mark.components
@pytest.mark.providers
@pytest.mark.forex
@pytest.mark.forex_oanda
class TestOandaForexProvider:
    def _oanda_pattern(self):
        return re.compile(r"^https://fxds-public-exchange-rates-api\.oanda\.com/cc-api/currencies(\?.*)?$")

    def test_get_daily_rate_parses_average_bid(self, oanda_provider, requests_mock):
        requests_mock.get(
            self._oanda_pattern(),
            json={
                "response": [
                    {
                        "average_bid": "0.859510",
                        "base_currency": "USD",
                        "quote_currency": "EUR",
                        "close_time": "2025-08-11T23:59:59Z",
                    }
                ]
            },
            status_code=200,
        )

        test_date = datetime.date(2025, 8, 12)
        rate = oanda_provider.get_daily_rate(source="usd", target="eur", date=test_date)
        assert isinstance(rate, Decimal)
        assert rate == Decimal("0.859510")
        assert len(requests_mock.request_history) == 1

    def test_convert_currency_uses_rate(self, oanda_provider, requests_mock):
        requests_mock.get(
            self._oanda_pattern(),
            json={"response": [{"average_bid": "2.5"}]},
            status_code=200,
        )

        test_date = datetime.date(2025, 8, 12)
        amount = Decimal(100)

        converted = oanda_provider.convert_currency(amount, source="USD", target="EUR", date=test_date)
        assert isinstance(converted, DecimalCurrency)
        assert converted.currency == Currency("EUR")
        assert converted == 250

    def test_error_on_invalid_response(self, oanda_provider, requests_mock):
        requests_mock.get(
            self._oanda_pattern(),
            json={"invalid": []},
            status_code=200,
        )

        with pytest.raises(ValueError, match=r"Invalid response format"):
            oanda_provider.get_daily_rate(source="USD", target="EUR", date=datetime.date(2025, 8, 12))

    def test_error_on_http_failure(self, oanda_provider, requests_mock):
        requests_mock.get(
            self._oanda_pattern(),
            text="Server error",
            status_code=500,
        )

        with pytest.raises(ValueError, match=r"Failed to fetch exchange rate"):
            oanda_provider.get_daily_rate(source="USD", target="EUR", date=datetime.date(2025, 8, 12))

    def test_memoization_caches_results(self, oanda_provider, requests_mock):
        requests_mock.get(
            self._oanda_pattern(),
            json={"response": [{"average_bid": "1.2345"}]},
            status_code=200,
        )

        d = datetime.date(2025, 8, 12)
        r1 = oanda_provider.get_daily_rate(source="USD", target="EUR", date=d)
        r2 = oanda_provider.get_daily_rate(source="USD", target="EUR", date=d)
        assert r1 == r2 == Decimal("1.2345")
        assert len(requests_mock.request_history) == 1  # second call should hit lru_cache

    def test_forex_alias_gbx_to_gbp_short_circuits(self, oanda_provider, requests_mock):
        d = datetime.date(2025, 8, 12)
        rate = oanda_provider.get_daily_rate(source="GBX", target="GBP", date=d)
        assert rate == Decimal("0.01")
        assert len(requests_mock.request_history) == 0

    def test_forex_alias_gbp_to_gbx_short_circuits(self, oanda_provider, requests_mock):
        d = datetime.date(2025, 8, 12)
        rate = oanda_provider.get_daily_rate(source="GBP", target="GBX", date=d)
        assert rate == Decimal(100)
        assert len(requests_mock.request_history) == 0

    def test_get_daily_rate_usd_to_gbx_uses_gbp_pair_and_scales(self, oanda_provider, requests_mock):
        requests_mock.get(
            self._oanda_pattern(),
            json={
                "response": [
                    {
                        "average_bid": "0.80",
                        "base_currency": "USD",
                        "quote_currency": "GBP",
                        "close_time": "2025-08-11T23:59:59Z",
                    }
                ]
            },
            status_code=200,
        )

        d = datetime.date(2025, 8, 12)
        rate = oanda_provider.get_daily_rate(source="USD", target="GBX", date=d)

        assert rate == Decimal(80)  # 0.80 GBP per USD, scaled to pence
        assert len(requests_mock.request_history) == 1

    def test_get_daily_rate_gbx_to_usd_uses_gbp_pair_and_scales(self, oanda_provider, requests_mock):
        requests_mock.get(
            self._oanda_pattern(),
            json={
                "response": [
                    {
                        "average_bid": "1.25",
                        "base_currency": "GBP",
                        "quote_currency": "USD",
                        "close_time": "2025-08-11T23:59:59Z",
                    }
                ]
            },
            status_code=200,
        )

        d = datetime.date(2025, 8, 12)
        rate = oanda_provider.get_daily_rate(source="GBX", target="USD", date=d)

        assert rate == Decimal("0.0125")  # 1 GBX = 0.01 GBP
        assert len(requests_mock.request_history) == 1

    def test_convert_currency_usd_to_gbx_scales_amount(self, oanda_provider, requests_mock):
        requests_mock.get(
            self._oanda_pattern(),
            json={"response": [{"average_bid": "0.80"}]},
            status_code=200,
        )

        d = datetime.date(2025, 8, 12)
        converted = oanda_provider.convert_currency(Decimal(10), source="USD", target="GBX", date=d)
        assert converted.currency == Currency("GBX")
        assert converted == DecimalCurrency("800", currency="GBX")

    def test_convert_currency_gbx_to_usd_scales_amount(self, oanda_provider, requests_mock):
        requests_mock.get(
            self._oanda_pattern(),
            json={"response": [{"average_bid": "1.25"}]},
            status_code=200,
        )

        d = datetime.date(2025, 8, 12)
        converted = oanda_provider.convert_currency(DecimalCurrency("100", currency="GBX"), target="USD", date=d)
        assert converted.currency == Currency("USD")
        assert converted == DecimalCurrency("1.25", currency="USD")
