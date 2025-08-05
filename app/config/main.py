# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import Field

from ..components.providers import ProviderBaseConfig

from ..util.config import ConfigBase



# MARK: Main Config
class Config(ConfigBase):
    providers: dict[str, ProviderBaseConfig] = Field({})