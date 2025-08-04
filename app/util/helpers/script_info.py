# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import sys
import os
import re


def is_unit_test() -> bool:
    """
    Test whether running in a unit test environment.

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

    if env.lower() in ('false', '0', 'no'):
        return False

    return True


TRUST_EXE_NAME = False
DEFAULT_SCRIPT_NAME = 'pygaindalf.py'
def get_script_name() -> str:
    if TRUST_EXE_NAME and (not is_unit_test()) and len(sys.argv) > 0 and sys.argv[0]:
        exe_name = os.path.basename(sys.argv[0])
        return re.sub("\\.py$", '', exe_name, flags=re.I)
    return DEFAULT_SCRIPT_NAME


def get_script_home() -> str:
    if len(sys.argv) > 0 and sys.argv[0]:
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    else:
        return os.getcwd()