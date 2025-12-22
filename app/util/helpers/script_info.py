# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import os
import pathlib
import re
import sys


_IS_UNIT_TEST = None


def is_unit_test() -> bool:
    """Test whether running in a unit test environment.

    Returns:
        bool: True if running in a unit test environment, False otherwise.

    """
    global _IS_UNIT_TEST  # noqa: PLW0603

    if _IS_UNIT_TEST is not None:
        return _IS_UNIT_TEST

    _IS_UNIT_TEST = _is_unit_test()
    return _IS_UNIT_TEST


def _is_unit_test() -> bool:
    # Detect pytest
    if os.environ.get("PYTEST_VERSION", None) is not None:
        return True

    # Check UNIT_TEST environment variable
    env = os.environ.get("UNIT_TEST", None)
    if env is not None:
        env = env.strip()
    if not env:
        return False

    return env.lower() not in ("false", "0", "no")


def enable_extra_sanity_checks() -> bool:
    """Test whether to enable extra sanity checks while running (e.g., in unit tests).

    Returns:
        bool: True if extra checks should be enabled, False otherwise.

    """
    return __debug__ and is_unit_test()


def is_documentation_build() -> bool:
    """Test whether running in a documentation build environment.

    Returns:
        bool: True if running in a documentation build environment, False otherwise.

    """
    # Detect Sphinx documentation build
    return "sphinx" in sys.modules


TRUST_EXE_NAME = False
DEFAULT_EXE_NAME = "pygaindalf.py"


def get_exe_name() -> str:
    if TRUST_EXE_NAME and (not is_unit_test()) and len(sys.argv) > 0 and sys.argv[0]:
        return pathlib.Path(sys.argv[0]).name
    else:
        return DEFAULT_EXE_NAME


def get_script_name() -> str:
    exe_name = get_exe_name()
    return re.sub("\\.py$", "", exe_name, flags=re.IGNORECASE)


TRUST_SCRIPT_HOME = True


def get_script_home() -> pathlib.Path:
    if TRUST_SCRIPT_HOME and (not is_unit_test()) and len(sys.argv) > 0 and sys.argv[0]:
        return pathlib.Path(pathlib.Path(sys.argv[0]).resolve()).parent
    else:
        return pathlib.Path.cwd()
