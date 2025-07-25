# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging
from pydantic import BaseModel, field_validator, Field
from typing import override

LEVELS : dict[str, int] = {
    "CRITICAL": logging.CRITICAL,
    "ERROR"   : logging.ERROR   ,
    "WARNING" : logging.WARNING ,
    "INFO"    : logging.INFO    ,
    "DEBUG"   : logging.DEBUG   ,
    "NOTSET"  : logging.NOTSET  ,
}

REVERSE_LEVELS : dict[int, str] = {v: k for k, v in LEVELS.items()}


class LoggingLevel(BaseModel):
    value: int = logging.INFO

    def __init__(self, value: int):
        super().__init__(value=value)

    @field_validator('value', mode='before')
    @classmethod
    def coerce_value(cls, v) -> int:
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            v_upper = v.upper()
            if v_upper in LEVELS:
                return LEVELS[v_upper]
            try:
                # Try to parse string as integer
                return int(v)
            except ValueError:
                raise ValueError(f"Unknown logging level string: {v}")
        raise TypeError(f"Invalid type for logging level: {type(v)}")

    @property
    def name(self) -> str:
        return REVERSE_LEVELS.get(self.value, str(self.value))

    @override
    def __str__(self) -> str:
        name = REVERSE_LEVELS.get(self.value, None)
        if name is not None:
            return f"LoggingLevel.{name}"
        else:
            return f"LoggingLevel({self.value})"


class LoggingLevels(BaseModel):
    file: LoggingLevel = Field(LoggingLevel(-1), description="Log file level (-1 for no logging)")
    tty : LoggingLevel = Field(LoggingLevel(logging.INFO), description="Log level for TTY output")