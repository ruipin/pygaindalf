# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""Argument parsing and CLI option definitions for pygaindalf.

Defines global options, command actions, and wraps argparse for use throughout the application.
"""

from typing import override

from ..models.config_path import ConfigFilePath
from .parser import ArgParserBase


class DefaultArgParser(ArgParserBase):
    @override
    def initialize(self) -> None:
        # Configuration
        self.add("app.paths.config", type=ConfigFilePath, action="store", help="Configuration file to load")

        # Logging
        self.add(
            "logging.levels.file",
            "-lv",
            "--logfile-verbosity",
            action="store",
            help="Logfile verbosity. Can be numeric or one of the default logging levels (CRITICAL=50, ERROR=40, WARNING=30, INFO=20, DEBUG=10)",
        )

        self.add(
            "logging.levels.tty",
            "-cv",
            "--console-verbosity",
            action="store",
            help="Console verbosity. Can be numeric or one of the default logging levels (CRITICAL=50, ERROR=40, WARNING=30, INFO=20, DEBUG=10)",
        )

        self.add(
            "logging.levels.default",
            "-v",
            "--verbosity",
            action="store",
            help="Default verbosity. Can be numeric or one of the default logging levels (CRITICAL=50, ERROR=40, WARNING=30, INFO=20, DEBUG=10)",
        )

        self.add("logging.rich", "-r", "--rich", action="store_true", help="Use rich for console output")
        self.add("logging.rich", "-nr", "--no-rich", action="store_false", help="Do not use rich for console output")
