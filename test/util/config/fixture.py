# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Any

import pytest


class ConfigFixture:
    def __init__(self):
        from app.config import CFG

        self.config = CFG
        self.config.load({})

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
