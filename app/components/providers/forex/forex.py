# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime
from decimal import Decimal

from abc import ABCMeta, abstractmethod
from .. import component_entrypoint, ProviderBase, BaseProviderConfig, ComponentField


# MARK: Provider Base Configuration
class BaseForexProviderConfig(BaseProviderConfig, metaclass=ABCMeta):
    pass



# MARK: Provider Base class
class ForexProviderBase(ProviderBase, metaclass=ABCMeta):
    config = ComponentField(BaseForexProviderConfig)


    @abstractmethod
    @component_entrypoint
    def get_daily_rate(self, from_currency: str, to_currency: str, date: datetime.date) -> Decimal:
        """
        Get the daily exchange rate from one currency to another.
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abstractmethod
    @component_entrypoint
    def convert_currency(self, amount: Decimal, from_currency: str, to_currency: str, date: datetime.date) -> Decimal:
        """
        Convert an amount from one currency to another on a specific date.
        """
        raise NotImplementedError("This method should be implemented by subclasses.")