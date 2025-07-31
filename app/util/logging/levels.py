# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging
from pydantic_core import CoreSchema, core_schema
from pydantic import BaseModel, field_validator, Field, TypeAdapter, GetCoreSchemaHandler
from typing import override, Any, Self

LEVELS : dict[str, int] = {
    "CRITICAL": logging.CRITICAL,
    "ERROR"   : logging.ERROR   ,
    "WARNING" : logging.WARNING ,
    "INFO"    : logging.INFO    ,
    "DEBUG"   : logging.DEBUG   ,
    "NOTSET"  : logging.NOTSET  ,
    "OFF"     : -1,
}

REVERSE_LEVELS : dict[int, str] = {v: k for k, v in LEVELS.items()}


class LoggingLevel:
    def __init__(self, value: int):
        if not isinstance(value, int):
            value = self.__class__.coerce(value)
        self.value = value

    @classmethod
    def coerce(cls, value : Any) -> int:
        level = -1

        # Handle instance of cls as special case - simply return it
        if isinstance(value, LoggingLevel):
            return value.value

        # Coerce value to int
        if isinstance(value, str):
            # Check if this is a named level
            upper = value.upper()
            if upper in LEVELS:
                level = LEVELS[upper]
            elif upper == 'FALSE':
                level = -1
            else:
                # Try to parse as integer
                try:
                    level = int(value)
                except ValueError:
                    raise ValueError(f"Unknown logging level string: {value}")

        elif isinstance(value, bool):
            if value:
                level = logging.INFO
            else:
                level = -1

        elif not isinstance(value, int):
            raise TypeError(f"Invalid type for logging level: {type(value)}")

        if level < -1:
            raise ValueError(f"Invalid value for logging level: {level}")

        return level

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.with_info_after_validator_function(
            function= cls.validate,
            #schema= core_schema.any_schema(),
            schema= core_schema.union_schema([core_schema.int_schema(), core_schema.str_schema(), core_schema.bool_schema(), core_schema.none_schema()]),
            field_name=handler.field_name
        )

    @classmethod
    def validate(cls, value : Any, info : core_schema.ValidationInfo) -> 'LoggingLevel':
        # Handle 'None' value as a special case - rely on field default value
        if value is None:
            field_name = info.field_name
            if field_name is None:
                raise ValueError("Cannot coerce 'None' value when the field name under validation is unknown")

            field = LoggingLevels.model_fields.get(field_name, None)
            if field is None:
                raise ValueError("Cannot coerce 'None' value when field info was not found")

            value = field.default

        level = cls.coerce(value)

        # Return instance of class
        return cls(level)


    @property
    def name(self) -> str:
        return REVERSE_LEVELS.get(self.value, str(self.value))

    @override
    def __repr__(self) -> str:
        name = REVERSE_LEVELS.get(self.value, None)
        if name is not None:
            return f"LoggingLevel.{name}"
        else:
            return f"LoggingLevel({self.value})"

    @override
    def __str__(self) -> str:
        return repr(self)


class LoggingLevels(BaseModel):
    file: LoggingLevel = Field(LoggingLevel(     -1     ), description="Log level for log file output")
    tty : LoggingLevel = Field(LoggingLevel(logging.INFO), description="Log level for TTY output")
    root: LoggingLevel = Field(LoggingLevel(      0     ), description="Log level for the root log handler")