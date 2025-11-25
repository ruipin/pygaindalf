# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import os

from pathlib import Path
from typing import Annotated

from pydantic import AfterValidator
from pydantic.types import PathType


def expand_path(v: Path) -> Path:
    # Expand environment variables
    v = Path(os.path.expandvars(v.as_posix()))
    # Expand user home directory
    path = Path(v).expanduser()
    # Done
    return path  # noqa: RET504


def delete_file_path(v: Path) -> Path:
    if v.exists() and v.is_file():
        v.unlink()
    return v


EnvFilePath = Annotated[Path, AfterValidator(expand_path), PathType("file")]
EnvDirectoryPath = Annotated[Path, AfterValidator(expand_path), PathType("dir")]
EnvNewPath = Annotated[Path, AfterValidator(expand_path), PathType("new")]
EnvForceNewPath = Annotated[Path, AfterValidator(expand_path), AfterValidator(delete_file_path), PathType("new")]
