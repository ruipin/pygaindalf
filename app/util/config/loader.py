# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


import yaml
import argparse
import sys

from typing import Any

from ..mixins import LoggableMixin

from .models.config_path import ConfigFilePath
from ..helpers import script_info
from ..helpers import script_version

from ..logging.manager import LoggingManager

from .yaml_loader import IncludeLoader
from .models import ConfigLoggingOnly, ConfigBase
from ..requests import RequestsManager


class ConfigFileLoader[C: ConfigBase](LoggableMixin):
    def __init__(self, config_class: type[C], args : argparse.Namespace):
        self.config_class = config_class
        self.args = args
        self.config = None
        self.path = '-'


    def _merge_args(self) -> None:
        for name, value in vars(self.args).items():
            if value is None:
                continue

            split = name.split('.')
            if len(split) <= 0 or split[0] == 'app':
                continue

            # Key is in the form 'config.key.subkey.subsubkey.etc'
            # Traverse the data structure to find the right place to insert the value
            d : dict[str, Any] = self.data

            if len(split) > 1:
                for key in split[:-1]:
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


    def open(self, path : ConfigFilePath | str) -> C:
        if self.config is not None:
            raise RuntimeError("Configuration already loaded. Cannot load again.")

        if isinstance(path, str):
            path = ConfigFilePath(path)

        self.path = path

        with self.path.open() as f:
            # Load the YAML file
            data = yaml.load(f, IncludeLoader)

        if not isinstance(data, dict):
            raise TypeError(f"Invalid configuration file format. Expected a dictionary, got {type(self.data).__name__}")

        return self.load(data)


    def load(self, data : dict[str, Any] | str) -> C:
        if self.config is not None:
            raise RuntimeError("Configuration already loaded. Cannot load again.")

        if isinstance(data, str):
            self.data : dict[str, Any] = yaml.load(data, IncludeLoader)
        else:
            self.data = data

        # Merge the loaded data with the application arguments
        self._merge_args()

        # Use current state of data to initialize logging manager
        self._init_logging_manager()

        # Inject static configuration data
        if 'app' in self.data:
            raise RuntimeError("Configuration file contains 'app' section. This is reserved for internal use.")
        self.data['app'] = {
            'name': script_info.get_script_name(),
            'exe': script_info.get_exe_name(),
            'version': {
                'revision': script_version.git_revision,
                'version': script_version.version,
                'full': script_version.version_string
            },
            'paths': {
                'config': self.path,
                'home': script_info.get_script_home()
            },
            'test': script_info.is_unit_test()
        }

        # Log app header, arguments
        if not script_info.is_unit_test():
            self.log.info("****** %s %s ******", self.data['app']['name'], self.data['app']['version']['full'], extra={'simple': True})
            self.log.debug('Command line: %s', ' '.join(sys.argv))

        # Initialise the global configuration object
        self.config = self.config_class.model_validate(self.data)

        # Log configuration
        self.log.info("Configuration loaded successfully")
        if not script_info.is_unit_test():
            self.config.debug()

        # Initialize any other managers that depend on the configuration
        self._init_requests_manager()

        # Done
        return self.config


    def _init_logging_manager(self) -> None:
        if not script_info.is_unit_test():
            # Convert logging config entry into LoggingConfig object
            data = self.data.get('logging', {})
            config = ConfigLoggingOnly(logging=data)
            self.data['logging'] = config.logging

            # Initialize the logging manager with the config
            manager = LoggingManager()
            manager.initialize(config.logging)


    def _init_requests_manager(self) -> None:
        if self.config is None:
            raise RuntimeError("Configuration not loaded. Call 'load()' first.")

        manager = RequestsManager()

        # We only initialize the requests manager if it is not already initialized
        if manager.initialized:
            return
        manager.initialize(self.config.requests, install=True)