# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from pathlib import Path
from .levels import LoggingLevels
from pydantic import BaseModel, DirectoryPath, Field
from ..helpers.pydantic_lib import ConfigBaseModel


class LoggingConfig(ConfigBaseModel):
    dir: DirectoryPath = Field(default=Path.cwd(), description="Log file directory")
    levels: LoggingLevels = Field(default=LoggingLevels(), description="Logging levels configuration")
    rich: bool = Field(default=True, description="Enable rich text (colors etc) in TTY output")


class AppConfigLoggingOnly(BaseModel):
    logging: LoggingConfig = Field(default=LoggingConfig(), description="Logging configuration")