# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


import datetime

from http import HTTPStatus
from typing import TYPE_CHECKING, Any, override

import requests

from ....util.helpers import instance_lru_cache
from . import BaseForexProvider, BaseForexProviderConfig


if TYPE_CHECKING:
    from decimal import Decimal

    from iso4217 import Currency


# MARK: Configuration
class OandaForexProviderConfig(BaseForexProviderConfig):
    pass


# MARK: Provider
class OandaForexProvider(BaseForexProvider[OandaForexProviderConfig]):
    @instance_lru_cache(maxsize=128)
    @override
    def _get_daily_exchange_rate(self, from_currency: Currency, to_currency: Currency, date: datetime.date) -> Decimal:
        """Get the daily exchange rate."""
        url = "https://fxds-public-exchange-rates-api.oanda.com/cc-api/currencies"
        #         ?base=USD&quote=GBP&data_type=general_currency_pair&start_date=2025-08-05&end_date=2025-08-06'
        params: dict[str, Any] = {
            "base": from_currency.code.upper(),
            "quote": to_currency.code.upper(),
            "data_type": "general_currency_pair",
            "start_date": (date - datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
            "end_date": date.strftime("%Y-%m-%d"),
        }

        response = requests.get(url, params=params)

        if response.status_code != HTTPStatus.OK:
            self.log.error(t"Failed to fetch exchange rate ({response.status_code}): {response.text}")
            msg = f"Failed to fetch exchange rate for {from_currency} to {to_currency} on {date}"
            raise ValueError(msg)

        # We pick the average bid for the given date
        json = response.json()

        try:
            rate: str = str(json["response"][0]["average_bid"])
        except (KeyError, IndexError) as err:
            self.log.exception(t"Error parsing exchange rate data", exc_info=err)
            msg = f"Invalid response format for {from_currency} to {to_currency} on {date}: {json}"
            raise ValueError(msg) from err

        # Convert to Decimal
        result = self.decimal(rate)

        self.log.debug(t"Exchange rate for {from_currency} to {to_currency} on {date}: {result}")
        return result


COMPONENT = OandaForexProvider
