# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from iso4217 import Currency

from ....util.helpers import classproperty, instance_lru_cache
from .. import Provider, ProviderConfig, ProviderType, component_entrypoint


if TYPE_CHECKING:
    import datetime

    from decimal import Decimal


# MARK: Provider Base Configuration
class ForexProviderConfig(ProviderConfig, metaclass=ABCMeta):
    pass


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
        return self._get_daily_exchange_rate(source=source, target=target, date=date)

    @component_entrypoint
    def convert_currency(self, amount: Decimal, *, source: Currency | str, target: Currency | str, date: datetime.date) -> Decimal:
        source = self._validate_currency(source)
        target = self._validate_currency(target)
        rate = self._get_daily_exchange_rate(source=source, target=target, date=date)
        return amount * rate
