# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""
Argument parsing and CLI option definitions for pygaindalf
Defines global options, command actions, and wraps argparse for use throughout the application.
"""

import argparse
import os
import sys

from typing import Sequence, override
from abc import ABCMeta, abstractmethod

from ...helpers.script_info import get_script_name, is_unit_test, get_exe_name

###################
# Argument parser

ENV_PREFIX = get_script_name().upper()

class ArgParserBase(argparse.ArgumentParser, metaclass=ABCMeta):
    def __init__(self, *args, **kwargs):
        kwargs['prog'] = kwargs.get('prog', get_exe_name())
        kwargs['description'] = kwargs.get('description', "pygaindalf CLI options")
        kwargs['formatter_class'] = argparse.ArgumentDefaultsHelpFormatter

        super().__init__(*args, **kwargs)

        self.initialize()
        self.parse()

    @override
    def add_argument(self, name : str, *args, default=None, **kwargs) -> argparse.Action:
        """
        Add a command-line argument to the global parser.

        Args:
            name (str): The destination variable name.
            *args: Argument flags (e.g., '-v', '--verbosity').
            default: Default value if not set elsewhere.
            **kwargs: Additional argparse options.
        """

        env_name = name.upper().replace('.', '_')

        return super().add_argument(*args,
            dest=name,
            default=os.getenv(f"{ENV_PREFIX}_{env_name}", default),
            **kwargs
        )

    def add(self, *args, **kwargs) -> argparse.Action:
        return self.add_argument(*args, **kwargs)

    @abstractmethod
    def initialize(self) -> None:
        raise NotImplementedError("Subclasses must implement the 'initialize' method.")

    def get_argv(self) -> Sequence[str]:
        if is_unit_test():
            # In unit tests, we default to reading the config from stdin
            return ('-',)
        return sys.argv[1:]

    @override
    def parse_args(self, *args, **kwargs) -> argparse.Namespace:
        """
        Get the parsed command-line arguments.

        Returns:
            argparse.Namespace: The parsed arguments.
        """
        self.namespace = super().parse_args(self.get_argv(), *args, **kwargs)
        return self.namespace

    def parse(self, *args, **kwargs) -> argparse.Namespace:
        return self.parse_args(*args, **kwargs)