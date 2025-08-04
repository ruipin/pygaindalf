# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest
import logging
import os

from .fixture import ConfigFixture


@pytest.mark.config
class TestConfigLoader:
    def test_config_loads_yaml(self, config: ConfigFixture):
        config.load("""
            logging:
                levels:
                    tty: INFO
        """)

        # Check that config object has expected attributes
        assert hasattr(config, 'logging')
        assert hasattr(config, 'app')
        assert hasattr(config.app, 'name')
        assert isinstance(config.app.test, bool)
        # Check actual values
        assert config.logging.levels.tty == logging.INFO
        assert isinstance(config.app.name, str)
        assert isinstance(config.app.test, bool)

    def test_config_invalid_yaml(self, config: ConfigFixture):
        with pytest.raises(Exception):
            config.load("""
                any: text
            """)

    def test_config_missing_required_fields(self, config: ConfigFixture):
        # Remove 'logging' section
        with pytest.raises(Exception):
            config.load("""
                app:
                  name: test
            """)

    def test_config_invalid_log_level(self, config: ConfigFixture):
        # Set logging.level to an int instead of str
        with pytest.raises(Exception):
            config.load("""
                logging:
                  levels:
                    tty: banana
            """)

    def test_config_empty(self, config: ConfigFixture):
        with pytest.raises(Exception):
            config.load("")

    def test_config_load_from_file(self, tmp_path, config: ConfigFixture):
        config_path = os.path.join(tmp_path, "test.yaml")
        with open(config_path, 'w') as f:
            f.write("""
                logging:
                    levels:
                        tty: INFO
            """)

        config.open(config_path)

        assert hasattr(config, 'logging')
        assert config.logging.levels.tty == logging.INFO
        assert config.logging.levels.tty == 'INFO'
