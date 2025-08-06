# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from .forex import ForexProviderBase, BaseForexProviderConfig, ComponentField
import decimal


# MARK: Configuration
class OandaForexProviderConfig(BaseForexProviderConfig):
    pass



# MARK: Provider
class OandaForexProvider(ForexProviderBase):
    config = ComponentField(OandaForexProviderConfig)

    def __init__(self, config: OandaForexProviderConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)

        self.log.info(self.config_class)
        self.log.info(self.decimal.context)

        x = self.decimal('5.233232')
        y = self.decimal('2.112435')
        self.log.info(f"{x} * {y} = {x * y}")


COMPONENT = OandaForexProvider