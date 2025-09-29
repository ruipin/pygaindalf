# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import atexit
import logging
import sys

from typing import TYPE_CHECKING, override

from ..helpers import script_info


if TYPE_CHECKING:
    from . import manager


class ExitHandler(logging.Handler):
    """Custom logging handler to track log message counts and handle application exit status."""

    class ExitStatusFormatter(logging.Formatter):
        pass

    def atexit(self) -> None:
        """Handle application exit, print summary, and save config if appropriate."""
        self.in_atexit = True

        script_name = script_info.get_script_name()
        success = bool(self.num_error == 0 and self.num_critical == 0)

        # Prepare log message
        if success:
            if self.num_warning > 0:
                exit_str = f"\n****** {script_name} terminated with {self.num_warning} warning{'' if self.num_warning == 1 else 's'}! ******"
            else:
                exit_str = f"\n{script_name} terminated successfuly."
        else:
            errors = self.num_error + self.num_critical
            exit_str = (
                f"\n****** {script_name} terminated with {'an ' if errors == 1 else 'multiple'} error{'' if errors == 1 else 's'}! ******"
                f"\n  Warnings: {self.num_warning:6d}"
                f"\n  Errors:   {errors:6d}"
            )

        # Log to TTY
        print(exit_str, file=sys.stderr)  # noqa: T201 as this is an exit message

        # Log to file
        if self.manager.fh is not None:
            self.manager.fh.setFormatter(self.ExitStatusFormatter())
            logging.log(1000, exit_str, extra={"handler": "file"})  # noqa: LOG015 as this is an exit message

        # Done
        logging.shutdown()

    def __init__(self, manager: manager.LoggingManager, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.manager = manager

        self.in_atexit = False

        self.num_warning = 0
        self.num_error = 0
        self.num_critical = 0

        self.setLevel(logging.WARNING)
        atexit.register(self.atexit)

    @override
    def handle(self, record: logging.LogRecord) -> bool:
        if self.in_atexit:
            return False

        if record.levelno >= logging.CRITICAL:
            self.num_critical += 1
        elif record.levelno >= logging.ERROR:
            self.num_error += 1
        elif record.levelno >= logging.WARNING:
            self.num_warning += 1
        return True
