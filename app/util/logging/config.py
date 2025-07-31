# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from pathlib import Path
from .levels import LoggingLevels
from pydantic import BaseModel, DirectoryPath, Field
from ..config.pydantic_lib import ForbidExtraBaseModel

class LoggingConfig(ForbidExtraBaseModel):
    dir: DirectoryPath = Field(Path.cwd(), description="Log file directory")
    levels: LoggingLevels = Field(description="Logging levels configuration")
    rich: bool = Field(True, description="Enable rich text (colors etc) in TTY output")


class AppConfigLoggingOnly(BaseModel):
    logging: LoggingConfig = Field(description="Logging configuration")