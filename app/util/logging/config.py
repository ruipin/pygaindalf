# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import re

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from frozendict import frozendict
from pydantic import DirectoryPath, Field, field_validator

from ..config.models import BaseConfigModel
from ..helpers.frozendict import FrozenDict
from .levels import LoggingLevel


DEFAULT_CUSTOM_LEVELS: dict[str, LoggingLevel] = {
    r"^requests_cache": LoggingLevel.INFO,
    r"^urllib3\.connectionpool": LoggingLevel.INFO,
    r"^pdfminer": LoggingLevel.INFO,
}


class LoggingLevels(BaseConfigModel):
    file: LoggingLevel = Field(default=LoggingLevel.OFF, description="Log level for log file output")
    tty: LoggingLevel = Field(default=LoggingLevel.NOTSET, description="Log level for TTY output")
    root: LoggingLevel = Field(default=LoggingLevel.NOTSET, description="Log level for the root log handler")
    default: LoggingLevel = Field(default=LoggingLevel.INFO, description="Default log level for loggers not explicitly specified in 'custom'")

    custom: FrozenDict[re.Pattern[str], LoggingLevel] = Field(
        default_factory=dict,
        description="Custom logging levels, where the key is a regex for the logger name, and the value is the logging level.",
        validate_default=True,
    )

    @classmethod
    def _validate_regex_pattern(cls, pattern: Any) -> re.Pattern[str]:
        if isinstance(pattern, str):
            pattern = re.compile(pattern, re.IGNORECASE)
        if not isinstance(pattern, re.Pattern):
            msg = f"Custom logging levels keys must be str or compiled regex patterns, got {type(pattern)}"
            raise TypeError(msg)

        return pattern

    @field_validator("custom", mode="before")
    def compile_custom_level_patterns(cls, value: Any) -> FrozenDict[re.Pattern[str], LoggingLevel]:
        if not isinstance(value, Mapping):
            msg = f"Custom logging levels must be a dict, got {type(value)}"
            raise TypeError(msg)

        levels: Mapping[re.Pattern[str], LoggingLevel] = {}

        # Seed the custom levels with the default ones if they are not present
        for name, level in DEFAULT_CUSTOM_LEVELS.items():
            name = cls._validate_regex_pattern(name)
            levels[name] = level

        # Process the provided custom levels
        for name, level in value.items():
            name = cls._validate_regex_pattern(name)
            levels[name] = level

        # Return as frozendict
        return frozendict(levels)


class LoggingConfig(BaseConfigModel):
    dir: DirectoryPath = Field(default=Path.cwd(), description="Log file directory")
    levels: LoggingLevels = Field(default_factory=LoggingLevels, description="Logging levels configuration")
    rich: bool = Field(default=True, description="Enable rich text (colors etc) in TTY output")
