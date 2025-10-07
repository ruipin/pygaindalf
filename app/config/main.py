# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from frozendict import frozendict
from pydantic import Field

from ..components import BaseAgentConfig, BaseProviderConfig
from ..util.config import ConfigBase
from ..util.helpers.frozendict import FrozenDict
from .default import DefaultConfig


# MARK: Main Config
class Config(ConfigBase):
    default: DefaultConfig = Field(default_factory=DefaultConfig, description="Default configuration for the application")

    providers: FrozenDict[str, BaseProviderConfig] = Field(default_factory=frozendict, description="Dictionary of configured providers")

    components: tuple[BaseAgentConfig, ...] = Field(default_factory=tuple, description="Dictionary of configured components")
