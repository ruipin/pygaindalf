# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest

from app.portfolio.models import reset_state


@pytest.fixture(scope='function', autouse=True)
def reset_portfolio_state():
    """
    Reset global instance stores and registries to avoid cross-test contamination.
    """
    reset_state()
    yield
    reset_state()
