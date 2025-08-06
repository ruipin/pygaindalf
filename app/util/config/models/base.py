# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging

from reprlib import Repr
from pydantic import Field

from .logging import LoggingConfig
from .app_info import AppInfo
from .base_model import BaseConfigModel

from ...mixins import LoggableMixin

class ConfigLoggingOnly(BaseConfigModel):
    logging: LoggingConfig = Field(default=LoggingConfig(), description="Logging configuration")

class ConfigBase(ConfigLoggingOnly, LoggableMixin):
    app: AppInfo = Field(description="Application information, automatically gathered at startup")

    def debug(self) -> None:
        model_dump = None

        # TTY
        if self.log.isEnabledForTty(logging.DEBUG):
            if self.logging.rich:
                from rich import pretty
                pretty.pprint(self, indent_guides=True, expand_all=True)
            else:
                model_dump = self.model_dump()
                self.log.debug(Repr(indent=4).repr(model_dump), extra={'handler': 'tty'})

        # File
        if self.log.isEnabledForFile(logging.DEBUG):
            if model_dump is None:
                model_dump = self.model_dump()
            self.log.debug("Configuration: %s", Repr(indent=4).repr(model_dump), extra={'handler': 'file'})