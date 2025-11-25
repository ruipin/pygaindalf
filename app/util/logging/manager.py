# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""Logging configuration and utilities for pygaindalf.

Configures file and TTY logging, log levels, and custom handlers.
"""

import logging
import pathlib
import re
import sys

from typing import TYPE_CHECKING, Any, ClassVar, Self
from typing import cast as typing_cast

from ..config.models import LoggingConfig
from ..helpers import script_info
from .exit_handler import ExitHandler
from .filters import HandlerFilter
from .formatters import ConditionalFormatter


if TYPE_CHECKING:
    from .levels import LoggingLevel


######
# MARK: Constants

# Log file name
LOG_FILE_NAME: str = f"{script_info.get_script_name()}.log"


######
# MARK: Logging Manager
class LoggingManager:
    _instance: ClassVar[LoggingManager | None] = None

    def __new__(cls, *args, **kwargs) -> Self:
        if (instance := cls._instance) is None:
            instance = cls._instance = super().__new__(cls, *args, **kwargs)
            instance.initialized = False
        return typing_cast("Self", instance)

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
        self._configure_exception_handler()
        self._configure_custom_logger_levels()

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

    def _configure_exception_handler(self) -> None:
        if self.config.rich:
            from rich.traceback import install

            from app.util import callguard

            install(
                extra_lines=1,
                suppress=(callguard,),
                code_width=160,
                width=200,
                show_locals=True,
                locals_hide_dunder=True,
                word_wrap=False,
            )

    def apply_logging_level(self, logger: logging.Logger) -> None:
        # Do nothing if logger already has an explicit level set
        if logger.level != logging.NOTSET:
            return

        # Determine logger name
        name = logger.name

        # Apply the most specific matching custom level, or default if none match
        level: LoggingLevel = self.config.levels.default
        pattern_len = 0

        for _pattern, _level in self.config.levels.custom.items():
            assert isinstance(_pattern, re.Pattern), f"Custom logging levels keys must be compiled regex patterns, got {type(_pattern)}"
            if (match := _pattern.match(name)) is not None:
                _pattern_len = len(match.group(0))
                if pattern_len < _pattern_len:
                    level = _level
                    pattern_len = _pattern_len

        if level == logging.NOTSET:
            return

        logger.setLevel(level.value)

    def _configure_custom_logger_levels(self) -> None:
        # Apply logging levels to existing loggers
        for logger_name in logging.root.manager.loggerDict:
            logger = logging.getLogger(logger_name)
            self.apply_logging_level(logger)
