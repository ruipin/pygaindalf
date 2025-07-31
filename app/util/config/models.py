# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging

from pathlib import Path
from .pydantic_lib import ForbidExtraBaseModel

from ..logging.config import LoggingConfig


class AppConfig(ForbidExtraBaseModel):
    logging: LoggingConfig
