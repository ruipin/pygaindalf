# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


# This file can be used to define pytest fixtures for the test suite.
# Currently empty, but required for pytest to recognize the test directory as a package.
from doctest import ELLIPSIS, IGNORE_EXCEPTION_DETAIL

from sybil import Sybil
from sybil.parsers.rest import DocTestParser, PythonCodeBlockParser

from test.components.fixture import *
from test.util.config.fixture import *


pytest_collect_file = Sybil(
    parsers=[
        DocTestParser(optionflags=ELLIPSIS | IGNORE_EXCEPTION_DETAIL),
        PythonCodeBlockParser(),
    ],
    patterns=["*.rst", "*.py"],
).pytest()
