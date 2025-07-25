# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging

from pathlib import Path
from pydantic import BaseModel, DirectoryPath, Field

from ..logging.config import LoggingConfig


class AppConfig(BaseModel):
    logging: LoggingConfig
