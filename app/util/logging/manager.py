# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""
Logging configuration and utilities for pyddcci.
Configures file and TTY logging, log levels, and custom handlers.
"""

import logging
import sys
import os

from typing import override, Protocol, runtime_checkable

from .exit_handler import ExitHandler

from ..helpers.script_info import get_script_name, is_unit_test

from app.util.logging.config import LoggingConfig

######
# MARK: Constants

# Log file name
LOG_FILE_NAME : str = f"{get_script_name()}.log"


######
# MARK: Logging Manager
class LoggingManager:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LoggingManager, cls).__new__(cls, *args, **kwargs)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        pass

    def initialize(self, config : LoggingConfig):
        if self.initialized:
            raise RuntimeError("Must not initialise LoggingManager twice")
        self.initialized = True

        self.config = config
        self.log_file_path = os.path.join(config.dir, LOG_FILE_NAME)

        self._configure_root_logger ()
        self._configure_file_handler()
        self._configure_tty_handler ()
        self._configure_exit_handler()

    def _configure_root_logger(self) -> None:
        """
            Configure root logger
        """
        logging.captureWarnings(True)
        logging.root.setLevel(self.config.levels.root.value)

    def _configure_file_handler(self) -> None:
        self.fh = None
        if self.config.levels.file.value < 0:
            return

        if not os.path.exists(self.log_file_path):
            os.makedirs(self.log_file_path)

        self.fh = logging.FileHandler(self.log_file_path, mode='w')
        self.fh.setLevel(self.config.levels.file.value)
        self.fh_formatter = logging.Formatter('%(asctime)s [%(levelname)s:%(name)s] %(message)s')
        self.fh.setFormatter(self.fh_formatter)
        logging.root.addHandler(self.fh)

    def _configure_tty_handler(self) -> None:
        self.ch = None
        if self.config.levels.tty.value < 0:
            return

        # Create console handler
        if self.config.rich:
            from .rich_handler import CustomRichHandler
            self.ch = CustomRichHandler()
        else:
            # The unittest module mocks stderr when the test starts, so we need to dynamically use sys.stderr instead of being able to use the current sys.stderr
            # REVISIT : is this needed for pytest?
            if is_unit_test():
                class UnitTestStreamHandler(logging.StreamHandler):
                    @property
                    @override
                    def stream(self):
                        return sys.stderr

                    @stream.setter
                    def stream(self, value):
                        pass
                self.ch = UnitTestStreamHandler()
            else:
                self.ch = logging.StreamHandler(sys.stderr)
            self.ch_formatter = logging.Formatter('[%(levelname).1s:%(name)s] %(message)s')
            self.ch.setFormatter(self.ch_formatter)

        self.ch.setLevel(self.config.levels.tty.value)
        logging.root.addHandler(self.ch)

    def _configure_exit_handler(self) -> None:
        self.eh = ExitHandler(self)
        logging.root.addHandler(self.eh)