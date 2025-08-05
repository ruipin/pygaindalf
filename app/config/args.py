# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""
Argument parsing and CLI option definitions for pygaindalf
Defines global options, command actions, and wraps argparse for use throughout the application.
"""

from typing import override

from . import DefaultArgParser

class ArgParser(DefaultArgParser):
    @override
    def initialize(self) -> None:
        super().initialize()
        # Additional initialization can be done here if needed

