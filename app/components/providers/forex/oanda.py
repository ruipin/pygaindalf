# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from . import ForexProviderBase, BaseForexProviderConfig, ComponentField, component_entrypoint

import requests
import datetime
import functools

from decimal import Decimal
from typing import override, Any


# MARK: Configuration
class OandaForexProviderConfig(BaseForexProviderConfig):
    pass



# MARK: Provider
class OandaForexProvider(ForexProviderBase):
    config = ComponentField(OandaForexProviderConfig)

    def __init__(self, config: OandaForexProviderConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)


    @functools.lru_cache(maxsize=128)
    def _get_daily_exchange_rate(self, from_currency: str, to_currency: str, date: datetime.date) -> Decimal:
        """
        Internal method to get the daily exchange rate.
        This is a placeholder for the actual implementation.
        """
        url = 'https://fxds-public-exchange-rates-api.oanda.com/cc-api/currencies'
        #         ?base=USD&quote=GBP&data_type=general_currency_pair&start_date=2025-08-05&end_date=2025-08-06'
        params : dict[str, Any] = {
            'base': from_currency.upper(),
            'quote': to_currency.upper(),
            'data_type': 'general_currency_pair',
            'start_date': (date - datetime.timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': date.strftime('%Y-%m-%d'),
        }

        response = requests.get(url, params=params)

        if response.status_code != 200:
            self.log.error(f"Failed to fetch exchange rate ({response.status_code}): {response.text}")
            raise ValueError(f"Failed to fetch exchange rate for {from_currency} to {to_currency} on {date}")

        # We pick the average bid for the given date
        json = response.json()

        try:
            rate : str = str(json['response'][0]['average_bid'])
        except (KeyError, IndexError) as e:
            self.log.error(f"Error parsing exchange rate data: {e}")
            raise ValueError(f"Invalid response format for {from_currency} to {to_currency} on {date}: {json}")

        # Convert to Decimal
        result = self.decimal(rate)

        self.log.debug(f"Exchange rate for {from_currency} to {to_currency} on {date}: {result}")
        return result


    @override
    @component_entrypoint
    def get_daily_rate(self, from_currency: str, to_currency: str, date: datetime.date) -> Decimal:
        return self._get_daily_exchange_rate(from_currency, to_currency, date)

    @override
    @component_entrypoint
    def convert_currency(self, amount: Decimal, from_currency: str, to_currency: str, date: datetime.date) -> Decimal:
        rate = self._get_daily_exchange_rate(from_currency, to_currency, date)
        return amount * rate

COMPONENT = OandaForexProvider