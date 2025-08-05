# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


import logging

from typing import Any
from pydantic import DirectoryPath, Field
from reprlib import Repr

from .. import LoggableMixin

from ..args.config_path import ConfigFilePath
from ..helpers.pydantic_lib import ConfigBaseModel

from ..logging.config import LoggingConfig


# MARK: App Config
class VersionConfig(ConfigBaseModel):
    version : str
    revision : str | None
    full : str

class PathsConfig(ConfigBaseModel):
    config : ConfigFilePath
    home : DirectoryPath


class AppConfig(ConfigBaseModel):
    name : str
    exe : str
    version : VersionConfig
    paths : PathsConfig
    test : bool



# MARK: Main Config
class Config(ConfigBaseModel, LoggableMixin):
    app: AppConfig
    logging: LoggingConfig = Field(default=LoggingConfig())


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