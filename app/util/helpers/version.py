# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""
Version and revision utilities for pygaindalf
Provides version string and git revision helpers.
"""

import os
import subprocess

from functools import cached_property

from ..args.config_path import override


# Constants
VERSION = "0.1"
GIT_ABBREV = 9  # Abbreviation length for git revision

# ScriptVersion class
class ScriptVersion:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ScriptVersion, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        pass

    def _minimal_ext_cmd(self, cmd) -> str|None:
        # construct minimal environment
        env = {}
        for k in ['SYSTEMROOT', 'PATH']:
            v = os.environ.get(k)
            if v is not None:
                env[k] = v

        # LANGUAGE is used on win32
        env['LANGUAGE'] = 'C'
        env['LANG'] = 'C'
        env['LC_ALL'] = 'C'

        _out = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env).communicate()
        if _out[1]:
            return None
        return _out[0].strip().decode('ascii')

    @cached_property
    def git_revision(self) -> str|None:
        """
        Get the current git revision string, if available.

        Returns:
            str or None: The git revision string, or None if not available.
        """
        try:
            return self._minimal_ext_cmd([
                    'git', 'describe',
                    '--exclude', '*',
                    '--always',
                    '--broken',
                    '--dirty',
                    f'--abbrev={GIT_ABBREV}'
                ])
        except OSError:
            return None

    @property
    def version(self) -> str:
        return VERSION

    @cached_property
    def version_string(self) -> str:
        """
        Get the full version string, including git revision if available.

        Returns:
            str: The version string.
        """
        ver = VERSION

        git_revision = self.git_revision
        if git_revision:
            ver += f"-{git_revision}"

        return ver

    @override
    def __str__(self) -> str:
        return self.version_string

    @override
    def __repr__(self) -> str:
        return f"<ScriptVersion: {str(self)}>"