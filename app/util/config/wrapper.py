# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from functools import cached_property
from typing import TYPE_CHECKING, Any

from ..helpers import script_info
from .args import ArgParserBase
from .loader import ConfigFileLoader
from .models import ConfigBase, ConfigFilePath


if TYPE_CHECKING:
    import argparse


class ConfigWrapper[C: ConfigBase, A: ArgParserBase]:
    def __init__(self, config_class: type[C], argparser_class: type[A]) -> None:
        self.config_class = config_class
        self.argparser_class = argparser_class
        self.config = None

    def initialize(self) -> C:
        return self.open(getattr(self.args, "app.paths.config"))

    @cached_property
    def args(self) -> argparse.Namespace:
        parser = self.argparser_class()
        return parser.parse_args()

    def open(self, path: ConfigFilePath | str) -> C:
        loader = ConfigFileLoader(self.config_class, self.args)
        self.config = loader.open(path)
        return self.config

    def load(self, config: str | dict[str, Any] | C) -> C:
        if isinstance(config, self.config_class):
            self.config = config
        elif isinstance(config, (str, dict)):
            loader = ConfigFileLoader(self.config_class, self.args)
            self.config = loader.load(config)
        else:
            msg = f"Expected Config or dict, got {type(config).__name__}"
            raise TypeError(msg)
        return self.config

    def reset(self) -> None:
        if not script_info.is_unit_test():
            msg = "Cannot reset configuration outside of unit tests"
            raise RuntimeError(msg)
        self.config = None

    def __getattr__(self, name: str) -> Any:
        try:
            return super().__getattr__(name)  # pyright: ignore[reportAttributeAccessIssue]
        except AttributeError as err:
            if script_info.is_documentation_build():
                msg = f"Configuration not initialized. Cannot access '{name}'"
                raise AttributeError(msg) from err
            if self.config is None:
                msg = "Configuration not initialized. Call 'initialize()' first."
                raise RuntimeError(msg) from err
            return getattr(self.config, name)
