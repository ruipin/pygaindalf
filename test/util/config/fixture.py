# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest

from typing import Any

class ConfigFixture:
    def __init__(self):
        from app.util.config import CFG
        self.config = CFG
        self.config.load({})

    def cleanup(self):
        self.config.reset()

    def __getattr__(self, name) -> Any:
        if self.config is None:
            raise RuntimeError("Configuration not initialized. Call 'initialize()' first.")
        return getattr(self.config, name)



@pytest.fixture(scope='function')
def config():
    fixture = ConfigFixture()
    yield fixture
    fixture.cleanup()