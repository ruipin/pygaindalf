# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import DirectoryPath

from .config_path import ConfigFilePath
from . import BaseConfigModel


class VersionInfo(BaseConfigModel):
    version : str
    revision : str | None
    full : str

class PathsInfo(BaseConfigModel):
    config : ConfigFilePath
    home : DirectoryPath

class AppInfo(BaseConfigModel):
    name : str
    exe : str
    version : VersionInfo
    paths : PathsInfo
    test : bool