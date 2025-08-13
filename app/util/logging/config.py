# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging

from pathlib import Path
from pydantic import Field, DirectoryPath, field_validator

from ..config.models import BaseConfigModel

from .levels import LoggingLevel


DEFAULT_CUSTOM_LEVELS : dict[str, LoggingLevel] = {
    "requests_cache"        : LoggingLevel.INFO,
    "urllib3.connectionpool": LoggingLevel.INFO,
}


class LoggingLevels(BaseConfigModel):
    file: LoggingLevel = Field(default=LoggingLevel.OFF   , description="Log level for log file output")
    tty : LoggingLevel = Field(default=LoggingLevel.INFO  , description="Log level for TTY output")
    root: LoggingLevel = Field(default=LoggingLevel.NOTSET, description="Log level for the root log handler")

    custom: dict[str, LoggingLevel] = Field(default_factory=dict, description="Custom logging levels, where the key is the logger name and the value is the logging level.", validate_default=True)

    @field_validator('custom', mode='after')
    def add_default_custom_levels(cls, value: dict[str, LoggingLevel]) -> dict[str, LoggingLevel]:
        # Seed the custom levels with the default ones if they are not present
        for name, level in DEFAULT_CUSTOM_LEVELS.items():
            if name not in value:
                value[name] = level

        # Ensure the root logger is not included in custom levels
        if 'root' in value:
            raise ValueError("Custom logging levels must not include 'root' logger. Use the 'root' field instead.")

        return value


class LoggingConfig(BaseConfigModel):
    dir: DirectoryPath = Field(default=Path.cwd(), description="Log file directory")
    levels: LoggingLevels = Field(default=LoggingLevels(), description="Logging levels configuration")
    rich: bool = Field(default=True, description="Enable rich text (colors etc) in TTY output")