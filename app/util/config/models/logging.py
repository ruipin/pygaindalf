# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from pathlib import Path

from pydantic import Field, DirectoryPath

from . import BaseConfigModel

from .logging_levels import LoggingLevels


class LoggingConfig(BaseConfigModel):
    dir: DirectoryPath = Field(default=Path.cwd(), description="Log file directory")
    levels: LoggingLevels = Field(default=LoggingLevels(), description="Logging levels configuration")
    rich: bool = Field(default=True, description="Enable rich text (colors etc) in TTY output")
