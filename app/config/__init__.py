# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from ..util.config import ConfigWrapper
from .args import ArgParser
from .main import Config


# Export configuration wrapper
CFG = ConfigWrapper(Config, ArgParser)


__all__ = [
    "CFG",
    "ArgParser",
    "Config",
]
