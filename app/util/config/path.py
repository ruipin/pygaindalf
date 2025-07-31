# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import sys
import os
from io import TextIOBase
from typing import Any, override


class ConfigFilePath:
    def __init__(self, input : Any):
        if not isinstance(input, str):
            raise TypeError(f"Expected a string, got {type(input).__name__}")

        # Standard input
        if input != '-' and not os.path.isfile(input):
            raise FileNotFoundError(f"Configuration file not found: {input}")
        self.file_path = input

    def open(self, mode: str = 'r', encoding: str = 'UTF-8') -> TextIOBase:
        if self.is_stdin:
            if not isinstance(sys.stdin, TextIOBase):
                raise TypeError("Standard input is not a text stream")
            return sys.stdin
        else:
            return open(self.file_path, mode='r', encoding='UTF-8')


    @property
    def is_stdin(self) -> bool:
        return self.file_path == '-'

    @property
    def dirname(self) -> str:
        if self.is_stdin:
            return os.getcwd()
        return os.path.dirname(os.path.abspath(self.file_path))


    @override
    def __str__(self) -> str:
        return self.file_path

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.file_path})"