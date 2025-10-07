# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Any

import pytest

from app.config import ConfigManager


class ConfigFixture:
    def __init__(self):
        from app.config import CFG

        self.config = CFG
        self.config.load({})

    def create(self, data: dict[str, Any]) -> ConfigManager:
        """Reset and load the configuration with the provided data."""
        self.config.reset()
        self.config.load(data)
        return self.config

    def get(self) -> ConfigManager:
        if (config := self.config) is None:
            msg = "Configuration not initialized. Call 'create()' first."
            raise RuntimeError(msg)
        return config

    def cleanup(self):
        self.config.reset()

    def __getattr__(self, name) -> Any:
        if self.config is None:
            msg = "Configuration not initialized. Call 'initialize()' first."
            raise RuntimeError(msg)
        return getattr(self.config, name)


@pytest.fixture
def config():
    fixture = ConfigFixture()
    yield fixture
    fixture.cleanup()
