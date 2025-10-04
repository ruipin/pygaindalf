# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import sys

from io import TextIOBase
from pathlib import Path
from typing import Any, override

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


class ConfigFilePath:
    def __init__(self, stdin: Any) -> None:
        if not isinstance(stdin, str):
            msg = f"Expected a string, got {type(input).__name__}"
            raise TypeError(msg)

        # Standard input
        if stdin != "-" and not Path(stdin).is_file():
            msg = f"Configuration file not found: {stdin}"
            raise FileNotFoundError(msg)
        self.file_path = Path(stdin) if stdin != "-" else "-"

    def open(self, encoding: str = "UTF-8") -> TextIOBase:
        if self.is_stdin:
            if not isinstance(sys.stdin, TextIOBase):
                msg = "Standard input is not a text stream"
                raise TypeError(msg)
            return sys.stdin
        else:
            return Path(self.file_path).open(mode="r", encoding=encoding)

    @property
    def is_stdin(self) -> bool:
        return self.file_path == "-"

    @property
    def dirname(self) -> Path:
        if self.is_stdin:
            return Path.cwd()
        return Path(Path(self.file_path).resolve()).parent

    @classmethod
    def __get_pydantic_core_schema__(cls, source: type[Any], handler: GetCoreSchemaHandler) -> CoreSchema:
        assert source is cls, f"Expected source to be {cls.__name__}, got {source.__name__} instead."
        return core_schema.no_info_after_validator_function(
            function=cls._pydantic_validate,
            schema=core_schema.union_schema([core_schema.str_schema(), core_schema.is_instance_schema(cls)]),
            serialization=core_schema.plain_serializer_function_ser_schema(cls._pydantic_serialize, info_arg=True),
        )

    @classmethod
    def _pydantic_validate(cls, value: Any) -> ConfigFilePath:
        if isinstance(value, cls):
            return value
        return cls(value)

    @classmethod
    def _pydantic_serialize(cls, value: Any) -> str:
        if isinstance(value, cls):
            return str(value)
        elif isinstance(value, str):
            return value
        else:
            msg = f"Expected a ConfigFilePath or string, got {type(value).__name__}"
            raise TypeError(msg)

    @override
    def __str__(self) -> str:
        if isinstance(self.file_path, Path):
            return self.file_path.as_posix()
        else:
            return self.file_path

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self!s}')"
