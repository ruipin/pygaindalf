# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from .base import ForexProviderBase, ForexProviderBaseConfig, ComponentField


# MARK: Configuration
class OandaForexProviderConfig(ForexProviderBaseConfig):
    pass



# MARK: Provider
class OandaForexProvider(ForexProviderBase):
    config = ComponentField(OandaForexProviderConfig)

    def __init__(self, config: OandaForexProviderConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)

        self.log.info(self.config_class)


COMPONENT = OandaForexProvider