# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import sys
import os
from io import TextIOBase
from pathlib import Path

from typing import Any, override
from pydantic_core import CoreSchema, core_schema
from pydantic import BaseModel, field_validator, Field, TypeAdapter, GetCoreSchemaHandler


class ConfigFilePath:
    def __init__(self, input : Any):
        if not isinstance(input, str):
            raise TypeError(f"Expected a string, got {type(input).__name__}")

        # Standard input
        if input != '-' and not os.path.isfile(input):
            raise FileNotFoundError(f"Configuration file not found: {input}")
        self.file_path = Path(input) if input != '-' else '-'

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



    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.with_info_after_validator_function(
            function= cls.validate,
            schema= core_schema.union_schema([core_schema.str_schema(), core_schema.is_instance_schema(cls)]),
            field_name=handler.field_name,
            serialization=core_schema.plain_serializer_function_ser_schema(cls.serialize, info_arg=True),
        )

    @classmethod
    def validate(cls, value : Any, info : core_schema.ValidationInfo) -> 'ConfigFilePath':
        if isinstance(value, cls):
            return value
        return cls(value)

    @classmethod
    def serialize(cls, value: Any, info: core_schema.SerializationInfo) -> str:
        if isinstance(value, cls):
            return str(value)
        elif isinstance(value, str):
            return value
        else:
            raise TypeError(f"Expected a ConfigFilePath or string, got {type(value).__name__}")


    @override
    def __str__(self) -> str:
        if isinstance(self.file_path, Path):
            return self.file_path.as_posix()
        else:
            return self.file_path

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{str(self)}')"