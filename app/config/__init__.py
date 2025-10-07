# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from ..util.config import ConfigManager
from .args import ArgParser
from .main import Config


# Export configuration wrapper
CFG = ConfigManager(Config, ArgParser)


__all__ = [
    "CFG",
    "ArgParser",
    "Config",
]
