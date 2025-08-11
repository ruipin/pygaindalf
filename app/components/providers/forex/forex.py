# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta, abstractmethod
from pydantic import Field

from ....util.config.inherit import FieldInherit
from .. import ProviderBase, BaseProviderConfig, ComponentField
from ....util.helpers.decimal import DecimalConfig, DecimalFactory


# MARK: Provider Base Configuration
class BaseForexProviderConfig(BaseProviderConfig, metaclass=ABCMeta):
    decimal : DecimalConfig = FieldInherit(default=DecimalConfig(), description="Decimal configuration for provider")



# MARK: Provider Base class
class ForexProviderBase(ProviderBase, metaclass=ABCMeta):
    config = ComponentField(BaseForexProviderConfig)
    decimal = ComponentField(DecimalFactory)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.decimal = DecimalFactory(self.config.decimal)
        self.decimal.apply_context()