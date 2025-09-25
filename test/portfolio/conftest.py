# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest

from typing import Generator

from app.portfolio.models.entity import Entity
from app.portfolio.models.root import PortfolioRoot, EntityRoot
from app.portfolio.models.portfolio import Portfolio
from app.portfolio.models.store import EntityStore
from app.portfolio.journal.session_manager import SessionManager
from app.portfolio.models.portfolio import Portfolio


# Automatically provide a global EntityStore for all tests, that is not attached to any EntityRoot.
# This ensures that tests that rely on the global EntityStore by default (e.g. Entity UID assignment) have a valid entity store to work with.
# If tests wish to use the EntityRoot mechanisms (e.g. SessionManager), they should use the portfolio_root or entity_root fixtures, which will override this one.
@pytest.fixture(scope='function', autouse=True)
def autouse_entity_store() -> Generator[EntityStore]:
    # Ensure there is a default global EntityStore for tests that rely on it by default
    entity_store = EntityStore.create_global_store()
    yield entity_store
    EntityStore.clear_global_store()

@pytest.fixture(scope='function', autouse=True)
def autouse_entity_dependency_event_handlers() -> Generator[None]:
    yield
    Entity.clear_dependency_event_handlers()


# Provide a per-test PortfolioRoot and make it the global root so EntityStore/SessionManager
# resolve via get_global_store/get_global_manager.
@pytest.fixture(scope='function')
def portfolio_root() -> Generator[PortfolioRoot]:
    EntityStore.clear_global_store()

    if EntityRoot.get_global_root_or_none() is not None:
        raise RuntimeError("There is already a global EntityRoot instance. The portfolio_root fixture requires there to be no global EntityRoot instance.")

    root = PortfolioRoot.create_global_root()
    with root.session_manager(actor="portfolio_root fixture", reason="fixture setup"):
        root.portfolio = Portfolio()

    yield root

    PortfolioRoot.clear_global_root()


@pytest.fixture(scope='function')
def entity_root() -> Generator[EntityRoot]:
    EntityStore.clear_global_store()

    if EntityRoot.get_global_root_or_none() is not None:
        raise RuntimeError("There is already a global EntityRoot instance. The entity_root fixture requires there to be no global EntityRoot instance.")

    root = EntityRoot.create_global_root()

    yield root

    EntityRoot.clear_global_root()


@pytest.fixture(scope='function')
def entity_store() -> Generator[EntityStore]:
    yield EntityStore.get_global_store()


@pytest.fixture(scope='function')
def session_manager() -> SessionManager:
    return SessionManager.get_global_manager()
