# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Any

from .models import Config
from .loader import ConfigFileLoader

from ..helpers.script_info import is_unit_test
from ..args import ARGS
from ..args.config_path import ConfigFilePath


class ConfigWrapper:
    def __init__(self):
        self.config = None

    def initialize(self) -> None:
        self.open(getattr(ARGS, 'app.paths.config'))

    def open(self, path : ConfigFilePath | str) -> Config:
        loader = ConfigFileLoader()
        self.config = loader.open(path)
        return self.config

    def load(self, config : str | dict[str, Any] | Config):
        if isinstance(config, Config):
            self.config = config
        elif isinstance(config, (str,dict)):
            loader = ConfigFileLoader()
            self.config = loader.load(config)
        else:
            raise TypeError(f"Expected Config or dict, got {type(config).__name__}")
        return self.config

    def reset(self) -> None:
        if not is_unit_test():
            raise RuntimeError("Cannot reset configuration outside of unit tests")
        self.config = None

    def __getattr__(self, name) -> Any:
        if self.config is None:
            raise RuntimeError("Configuration not initialized. Call 'initialize()' first.")
        return getattr(self.config, name)