# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import os
import pathlib
import re
import sys


def is_unit_test() -> bool:
    """Test whether running in a unit test environment.

    Returns:
        bool: True if running in a unit test environment, False otherwise.

    """
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
