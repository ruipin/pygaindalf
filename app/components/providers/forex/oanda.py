# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


import requests
import datetime
import functools

from decimal import Decimal
from typing import override, Any
from iso4217 import Currency

from . import ForexProviderBase, BaseForexProviderConfig


# MARK: Configuration
class OandaForexProviderConfig(BaseForexProviderConfig):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        # Additional configuration parameters can be added here if needed
        # For now, we just call the parent constructor

    pass



# MARK: Provider
class OandaForexProvider(ForexProviderBase[OandaForexProviderConfig]):
    @functools.lru_cache(maxsize=128)
    @override
    def _get_daily_exchange_rate(self, from_currency: Currency, to_currency: Currency, date: datetime.date) -> Decimal:
        """
        Internal method to get the daily exchange rate.
        This is a placeholder for the actual implementation.
        """
        url = 'https://fxds-public-exchange-rates-api.oanda.com/cc-api/currencies'
        #         ?base=USD&quote=GBP&data_type=general_currency_pair&start_date=2025-08-05&end_date=2025-08-06'
        params : dict[str, Any] = {
            'base': from_currency.code.upper(),
            'quote': to_currency.code.upper(),
            'data_type': 'general_currency_pair',
            'start_date': (date - datetime.timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': date.strftime('%Y-%m-%d'),
        }

        response = requests.get(url, params=params)

        if response.status_code != 200:
            self.log.error(t"Failed to fetch exchange rate ({response.status_code}): {response.text}")
            raise ValueError(f"Failed to fetch exchange rate for {from_currency} to {to_currency} on {date}")

        # We pick the average bid for the given date
        json = response.json()

        try:
            rate : str = str(json['response'][0]['average_bid'])
        except (KeyError, IndexError) as e:
            self.log.error(t"Error parsing exchange rate data: {e}")
            raise ValueError(f"Invalid response format for {from_currency} to {to_currency} on {date}: {json}")

        # Convert to Decimal
        result = self.decimal(rate)

        self.log.debug(t"Exchange rate for {from_currency} to {to_currency} on {date}: {result}")
        return result

COMPONENT = OandaForexProvider