# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


import yaml

from typing import Any

from .path import ConfigFilePath
from .yaml_loader import IncludeLoader

from ..args import ARGS

from ..logging.config import AppConfigLoggingOnly
from ..logging.manager import LoggingManager


class ConfigFileParser:
    def __init__(self, path : str | ConfigFilePath):
        if isinstance(path, str):
            path = ConfigFilePath(path)

        self.path = path
        self._parse()


    def _merge_args(self) -> None:
        for name, value in vars(ARGS).items():
            split = name.split('.')
            if len(split) <= 0 or split[0] != 'config':
                continue

            # Key is in the form 'config.key.subkey.subsubkey.etc'
            # Traverse the data structure to find the right place to insert the value
            d : dict[str, Any] = self.data

            if len(split) > 1:
                for key in split[1:-1]:
                    next_d = d.get(key, None)

                    if not isinstance(next_d, dict):
                        next_d = {}
                        d[key] = next_d

                    d = next_d

            if d is None:
                raise RuntimeError(f"Failed to find the right place to insert the value for key '{key}' in the configuration data")

            # Now we are at the right place, insert the value
            key = split[-1]
            if isinstance(value, dict):
                current = d.get(key, None)
                if isinstance(current, dict):
                    current.update(value)
                    continue
            d[key] = value


    def _parse(self) -> None:
        with self.path.open() as f:
            # Load the YAML file
            self.data = yaml.load(f, IncludeLoader)

        if not isinstance(self.data, dict):
            raise TypeError(f"Invalid configuration file format. Expected a dictionary, got {type(self.data).__name__}")

        # Merge the loaded data with the application arguments
        self._merge_args()

        # Use current state of data to initialize logging manager
        self._init_logging_manager()

        # TODO : parse rest of config


    def _init_logging_manager(self) -> None:
        # Convert logging config entry into LoggingConfig object
        data = self.data.get('logging', {})
        config = AppConfigLoggingOnly(logging=data)
        self.data['logging'] = config.logging

        # Initialize logging manager
        manager = LoggingManager()
        manager.initialize(config.logging)