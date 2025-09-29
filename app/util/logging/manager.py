# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""Logging configuration and utilities for pygaindalf.

Configures file and TTY logging, log levels, and custom handlers.
"""

import logging
import pathlib
import sys

from typing import Any, Self

from ..config.models import LoggingConfig
from ..helpers import script_info
from .exit_handler import ExitHandler
from .filters import HandlerFilter
from .formatters import ConditionalFormatter


######
# MARK: Constants

# Log file name
LOG_FILE_NAME: str = f"{script_info.get_script_name()}.log"


######
# MARK: Logging Manager
class LoggingManager:
    _instance = None

    def __new__(cls, *args, **kwargs) -> Self:
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self) -> None:
        pass

    def initialize(self, config: LoggingConfig | dict[str, Any]) -> None:
        if not isinstance(config, LoggingConfig):
            config = LoggingConfig.model_validate(config)

        if self.initialized:
            msg = f"Must not initialise {type(self).__name__} twice"
            raise RuntimeError(msg)
        self.initialized = True

        self.config = config
        self.log_file_path = config.dir / LOG_FILE_NAME

        self._configure_root_logger()
        self._configure_file_handler()
        self._configure_tty_handler()
        self._configure_exit_handler()
        self._configure_custom_levels()

    def _configure_root_logger(self) -> None:
        """Configure root logger."""
        logging.captureWarnings(capture=True)

        logging.root.setLevel(self.config.levels.root.value)

    def _configure_file_handler(self) -> None:
        self.fh = None
        if self.config.levels.file.value < 0:
            return

        log_dir_path = pathlib.Path(self.log_file_path).parent
        if not pathlib.Path(log_dir_path).exists():
            pathlib.Path(log_dir_path).mkdir(parents=True)

        self.fh = logging.FileHandler(self.log_file_path, mode="w")
        self.fh.setLevel(self.config.levels.file.value)
        self.fh_formatter = ConditionalFormatter("%(asctime)s [%(levelname)s:%(name)s] %(message)s")
        self.fh.setFormatter(self.fh_formatter)
        logging.root.addHandler(self.fh)

        self.fh_filter = HandlerFilter("file")
        self.fh.addFilter(self.fh_filter)

    def _configure_tty_handler(self) -> None:
        self.ch = None
        if self.config.levels.tty.value < 0:
            return

        # Create console handler
        if self.config.rich:
            from .rich_handler import CustomRichHandler

            self.ch = CustomRichHandler()
        else:
            self.ch = logging.StreamHandler(sys.stderr)
            self.ch_formatter = ConditionalFormatter("[%(levelname).1s:%(name)s] %(message)s")
            self.ch.setFormatter(self.ch_formatter)

        self.ch.setLevel(self.config.levels.tty.value)

        if not script_info.is_unit_test():
            logging.root.addHandler(self.ch)

        self.ch_filter = HandlerFilter("tty")
        self.ch.addFilter(self.ch_filter)

    def _configure_exit_handler(self) -> None:
        # Exit handler is not needed for unit tests
        if script_info.is_unit_test():
            return

        self.eh = ExitHandler(self)
        logging.root.addHandler(self.eh)

    def _configure_custom_levels(self) -> None:
        """Configure custom loggers with the specified levels."""
        for name, level in self.config.levels.custom.items():
            logging.getLogger(name).setLevel(level.value)


# Handle unit tests - we just initialize the logging manager with minimal configuration
if script_info.is_unit_test():
    LoggingManager().initialize(
        {
            "levels": {
                "file": "OFF",
                "tty": "NOTSET",
            },
            "rich": False,
        }
    )
