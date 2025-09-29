# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""Version and revision utilities for pygaindalf.

Provides version string and git revision helpers.
"""

import os
import pathlib
import subprocess
import tomllib

from functools import cached_property
from typing import TYPE_CHECKING, Self, override

from .script_info import get_script_home


if TYPE_CHECKING:
    from collections.abc import Sequence


# Constants
GIT_ABBREV = 9  # Abbreviation length for git revision


# ScriptVersion class
class ScriptVersion:
    _instance = None

    def __new__(cls, *args, **kwargs) -> Self:
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self) -> None:
        pass

    def _minimal_ext_cmd(self, cmd: Sequence[str]) -> str | None:
        # construct minimal environment
        env = {}
        for k in ["SYSTEMROOT", "PATH"]:
            v = os.environ.get(k)
            if v is not None:
                env[k] = v

        # LANGUAGE is used on win32
        env["LANGUAGE"] = "C"
        env["LANG"] = "C"
        env["LC_ALL"] = "C"

        _out = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env).communicate()  # noqa: S603
        if _out[1]:
            return None
        return _out[0].strip().decode("ascii")

    @cached_property
    def git_revision(self) -> str | None:
        """Get the current git revision string, if available.

        Returns:
            str or None: The git revision string, or None if not available.

        """
        try:
            return self._minimal_ext_cmd(["git", "describe", "--exclude", "*", "--always", "--broken", "--dirty", f"--abbrev={GIT_ABBREV}"])
        except OSError:
            return None

    @property
    def version(self) -> str:
        pyproject_path = get_script_home() / "pyproject.toml"
        try:
            with pathlib.Path(pyproject_path).open("rb") as f:
                data = tomllib.load(f)
            return data["project"]["version"]
        except OSError:
            return "unknown"

    @cached_property
    def version_string(self) -> str:
        """Get the full version string, including git revision if available.

        Returns:
            str: The version string.

        """
        ver = self.version

        git_revision = self.git_revision
        if git_revision:
            ver += f"-{git_revision}"

        return ver

    @override
    def __str__(self) -> str:
        return self.version_string

    @override
    def __repr__(self) -> str:
        return f"<ScriptVersion: {self!s}>"


def __getattr__(key: str) -> str:
    attr = getattr(ScriptVersion(), key, None)
    if not isinstance(attr, str):
        msg = f"ScriptVersion has no attribute '{key}'"
        raise AttributeError(msg)  # noqa: TRY004
    return attr
