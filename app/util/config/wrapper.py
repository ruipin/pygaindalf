# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import argparse

from typing import Any
from functools import cached_property

from ..helpers import script_info

from .loader import ConfigFileLoader
from .models import ConfigBase, ConfigFilePath
from .args import ArgParserBase


class ConfigWrapper[C: ConfigBase, A: ArgParserBase]:
    def __init__(self, config_class : type[C], argparser_class : type[A]):
        self.config_class = config_class
        self.argparser_class = argparser_class
        self.config = None

    def initialize(self) -> C:
        return self.open(getattr(self.args, 'app.paths.config'))

    @cached_property
    def args(self) -> argparse.Namespace:
        parser = self.argparser_class()
        return parser.parse_args()

    def open(self, path : ConfigFilePath | str) -> C:
        loader = ConfigFileLoader(self.config_class, self.args)
        self.config = loader.open(path)
        return self.config

    def load(self, config : str | dict[str, Any] | C) -> C:
        if isinstance(config, self.config_class):
            self.config = config
        elif isinstance(config, (str,dict)):
            loader = ConfigFileLoader(self.config_class, self.args)
            self.config = loader.load(config)
        else:
            raise TypeError(f"Expected Config or dict, got {type(config).__name__}")
        return self.config

    def reset(self) -> None:
        if not script_info.is_unit_test():
            raise RuntimeError("Cannot reset configuration outside of unit tests")
        self.config = None

    def __getattr__(self, name) -> Any:
        try:
            return super().__getattr__(name)
        except AttributeError:
            if script_info.is_documentation_build():
                raise AttributeError(f"Configuration not initialized. Cannot access '{name}'")
            if self.config is None:
                raise RuntimeError("Configuration not initialized. Call 'initialize()' first.")
            return getattr(self.config, name)