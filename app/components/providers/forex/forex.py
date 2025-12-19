# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


import decimal

from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from iso4217 import Currency
from pydantic import Field

from ....util.helpers import classproperty, instance_lru_cache
from ....util.helpers.decimal_currency import DecimalCurrency
from .. import Provider, ProviderConfig, ProviderType, component_entrypoint


if TYPE_CHECKING:
    import datetime

    from decimal import Decimal


# MARK: Provider Base Configuration
class ForexProviderConfig(ProviderConfig, metaclass=ABCMeta):
    precision: int = Field(description="The number of decimal places for exchange rates", default=6)


# MARK: Provider Base class
class ForexProvider[C: ForexProviderConfig](Provider[C], metaclass=ABCMeta):
    @classproperty
    def default_key(cls) -> str:
        return ProviderType.FOREX

    @instance_lru_cache(maxsize=128)
    @abstractmethod
    def _get_daily_exchange_rate(self, *, source: Currency, target: Currency, date: datetime.date) -> Decimal:
        msg = "This method should be implemented by subclasses."
        raise NotImplementedError(msg)

    @classmethod
    def _validate_currency(cls, currency: Currency | str) -> Currency:
        if isinstance(currency, Currency):
            return currency
        if isinstance(currency, str):
            return Currency(currency.upper())
        msg = f"Expected Currency or str, got {type(currency).__name__}"
        raise TypeError(msg)

    @component_entrypoint
    def get_daily_rate(self, *, source: Currency | str, target: Currency | str, date: datetime.date) -> Decimal:
        source = self._validate_currency(source)
        target = self._validate_currency(target)
        rate = self._get_daily_exchange_rate(source=source, target=target, date=date)
        if self.config.precision < decimal.getcontext().prec:
            rate = round(rate, ndigits=self.config.precision)
        return rate

    @component_entrypoint
    def convert_currency(
        self,
        amount: Decimal | DecimalCurrency,
        *,
        source: Currency | str | None = None,
        target: Currency | str,
        date: datetime.date,
    ) -> DecimalCurrency:
        target = self._validate_currency(target)

        if amount.is_zero():
            return DecimalCurrency("0", currency=target)

        if isinstance(amount, DecimalCurrency):
            if source is None:
                source = amount.currency
        assert source is not None, "Source currency must be specified for non-zero amounts."

        if isinstance(amount, DecimalCurrency):
            source = self._validate_currency(source)
            if amount.currency != source:
                msg = "Currency mismatch between amount and specified source currency."
                raise ValueError(msg)
            amount = amount.decimal()
        else:
            source = self._validate_currency(source)

        rate = self._get_daily_exchange_rate(source=source, target=target, date=date)

        return DecimalCurrency(amount * rate, currency=target)
