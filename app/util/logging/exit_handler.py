# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import sys
import logging
import atexit

from typing import override
from ..helpers import script_info

from . import manager


class ExitHandler(logging.Handler):
    """
    Custom logging handler to track log message counts and handle application exit status.
    """
    class ExitStatusFormatter(logging.Formatter):
        @override
        def format(self, record):
            return record.msg


    def atexit(self):
        """
        Handle application exit, print summary, and save config if appropriate.
        """
        self.in_atexit = True

        script_name = script_info.get_script_name()
        success = True if self.num_error == 0 and self.num_critical == 0 else False

        # Prepare log message
        if success:
            if self.num_warning > 0:
                exit_str = f"\n****** {script_name} terminated with {self.num_warning} warning{'' if self.num_warning == 1 else 's'}! ******"
            else:
                exit_str = f"\n{script_name} terminated successfuly."
        else:
            errors = self.num_error + self.num_critical
            exit_str = \
                f"\n****** {script_name} terminated with {'an ' if errors == 1 else 'multiple'} error{'' if errors == 1 else 's'}! ******" \
                f"\n  Warnings: {self.num_warning:6d}" \
                f"\n  Errors:   {errors:6d}"

        # Log to TTY
        print(exit_str, file=sys.stderr)

        # Log to file
        if self.manager.fh is not None:
            self.manager.fh.setFormatter(self.ExitStatusFormatter())
            logging.log(1000, exit_str, extra={'handler': 'file'})

        # Done
        logging.shutdown()


    def __init__(self, manager : 'manager.LoggingManager', *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.manager = manager

        self.in_atexit = False

        self.num_warning = 0
        self.num_error = 0
        self.num_critical = 0

        self.setLevel(logging.WARNING)
        atexit.register(self.atexit)


    @override
    def handle(self, record) -> bool:
        if self.in_atexit:
            return False

        if record.levelno >= logging.CRITICAL:
            self.num_critical += 1
        elif record.levelno >= logging.ERROR:
            self.num_error += 1
        elif record.levelno >= logging.WARNING:
            self.num_warning += 1
        return True