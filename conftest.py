# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

# This file can be used to define pytest fixtures for the test suite and is required for pytest to recognize the test directory as a package.
from doctest import ELLIPSIS, IGNORE_EXCEPTION_DETAIL
from typing import TYPE_CHECKING

import pytest

from sybil import Sybil
from sybil.parsers.rest import DocTestParser, PythonCodeBlockParser

from test.components.fixture import *
from test.util.config.fixture import *


if TYPE_CHECKING:
    from app.util.logging.manager import LoggingManager


# Automatically provide a logging manager for all tests
@pytest.fixture(autouse=True, scope="session")
def logging_manager() -> LoggingManager:
    from app.util.logging.manager import LoggingManager

    manager = LoggingManager()
    manager.initialize(
        {
            "levels": {
                "file": "OFF",
                "tty": "NOTSET",
                "default": "NOTSET",
            },
            "rich": False,
        }
    )
    return manager


pytest_collect_file = Sybil(
    parsers=[
        DocTestParser(optionflags=ELLIPSIS | IGNORE_EXCEPTION_DETAIL),
        PythonCodeBlockParser(),
    ],
    patterns=["*.rst", "*.py"],
).pytest()
