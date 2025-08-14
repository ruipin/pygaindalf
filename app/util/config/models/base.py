# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging

from reprlib import Repr
from pydantic import Field
from typing import override, Any

from .app_info import AppInfo
from .base_model import BaseConfigModel

from ...logging.config import LoggingConfig
from ...mixins import LoggableMixin
from ...requests.config import RequestsConfig

class ConfigLoggingOnly(BaseConfigModel):
    logging: LoggingConfig = Field(default=LoggingConfig(), description="Logging configuration")

    @override
    def _seed_parent_and_name_to_object(self, name : str, obj : Any) -> None:
        # We need to override this method to avoid setting the parent and name when instantiating ConfigLoggingOnly but not its subclasses.
        # This is because ConfigLoggingOnly is used during the initialization of the logging system, and we do not want to set the parent and name
        # at that point. Otherwise, our sanity checks fail when the full configuration is loaded because the parent was already set.
        if self.__class__ is ConfigLoggingOnly:
            return
        super()._seed_parent_and_name_to_object(name, obj)

class ConfigBase(ConfigLoggingOnly):
    app: AppInfo = Field(description="Application information, automatically gathered at startup")

    requests : RequestsConfig = Field(default_factory=RequestsConfig, description="HTTP requests configuration, including rate limiting and caching")

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