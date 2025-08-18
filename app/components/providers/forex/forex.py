# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools
import datetime
from decimal import Decimal
from iso4217 import Currency

from abc import ABCMeta, abstractmethod
from .. import component_entrypoint, ProviderBase, BaseProviderConfig


# MARK: Provider Base Configuration
class BaseForexProviderConfig(BaseProviderConfig, metaclass=ABCMeta):
    pass



# MARK: Provider Base class
class ForexProviderBase[C : BaseForexProviderConfig](ProviderBase[C], metaclass=ABCMeta):
    @functools.lru_cache(maxsize=128)
    @abstractmethod
    def _get_daily_exchange_rate(self, from_currency: Currency, to_currency: Currency, date: datetime.date) -> Decimal:
        raise NotImplementedError("This method should be implemented by subclasses.")

    @classmethod
    def _validate_currency(cls, currency: Currency | str) -> Currency:
        if isinstance(currency, Currency):
            return currency
        if isinstance(currency, str):
            return Currency(currency.upper())
        raise TypeError(f"Expected Currency or str, got {type(currency).__name__}")

    @component_entrypoint
    def get_daily_rate(self, from_currency: Currency | str, to_currency: Currency | str, date: datetime.date) -> Decimal:
        from_currency = self._validate_currency(from_currency)
        to_currency   = self._validate_currency(to_currency  )
        return self._get_daily_exchange_rate(from_currency, to_currency, date)

    @component_entrypoint
    def convert_currency(self, amount: Decimal, from_currency: Currency | str, to_currency: Currency | str, date: datetime.date) -> Decimal:
        from_currency = self._validate_currency(from_currency)
        to_currency   = self._validate_currency(to_currency  )
        rate = self._get_daily_exchange_rate(from_currency, to_currency, date)
        return amount * rate