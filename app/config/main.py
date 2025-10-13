# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from frozendict import frozendict
from pydantic import Field

from ..components import AgentConfig, ProviderConfig
from ..util.config import ConfigBase
from ..util.helpers.frozendict import FrozenDict
from .default import DefaultConfig


# MARK: Main Config
class Config(ConfigBase):
    default: DefaultConfig = Field(default_factory=DefaultConfig, description="Default configuration for the application")

    providers: FrozenDict[str, ProviderConfig] = Field(default_factory=frozendict, description="Dictionary of configured providers")

    agents: tuple[AgentConfig, ...] = Field(default_factory=tuple, description="Tuple of configured agents")
