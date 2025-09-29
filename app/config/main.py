# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import Field

from ..components.providers import BaseProviderConfig
from ..util.config import ConfigBase
from .default import DefaultConfig


# MARK: Main Config
class Config(ConfigBase):
    default: DefaultConfig = Field(default_factory=DefaultConfig, description="Default configuration for the application")

    providers: dict[str, BaseProviderConfig] = Field({})
