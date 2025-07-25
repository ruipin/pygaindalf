# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from pathlib import Path
from .levels import LoggingLevels
from pydantic import BaseModel, DirectoryPath, Field

class LoggingConfig(BaseModel):
    dir: DirectoryPath = Field(Path.cwd(), description="Log file directory")
    levels: LoggingLevels = Field(description="Logging levels configuration")