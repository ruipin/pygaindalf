# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import DirectoryPath

from .config_path import ConfigFilePath
from . import ConfigBaseModel


class VersionInfo(ConfigBaseModel):
    version : str
    revision : str | None
    full : str

class PathsInfo(ConfigBaseModel):
    config : ConfigFilePath
    home : DirectoryPath

class AppInfo(ConfigBaseModel):
    name : str
    exe : str
    version : VersionInfo
    paths : PathsInfo
    test : bool