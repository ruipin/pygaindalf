# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest

from typing import Generator
from app.portfolio.models.store import EntityStore


@pytest.fixture(scope='function', autouse=True)
def entity_store() -> Generator[EntityStore]:
    store = EntityStore()
    store.reset()
    store.make_global_store()
    yield store
    store.reset()
