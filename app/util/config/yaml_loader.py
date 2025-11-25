# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import os
import pathlib

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import yaml


if TYPE_CHECKING:
    from io import IOBase


@runtime_checkable
class NamedYamlLoaderPathProtocol(Protocol):
    @property
    def name(self) -> str: ...


class IncludeLoader(yaml.SafeLoader):
    def __init__(self, stream: IOBase, root: pathlib.Path | None = None) -> None:
        if root is None:
            root = pathlib.Path(pathlib.Path(stream.name).resolve()).parent if isinstance(stream, NamedYamlLoaderPathProtocol) else pathlib.Path.cwd()

        self._root: pathlib.Path = root

        super().__init__(stream)

    def include(self, node: Any) -> Any:
        filename = self._root / self.construct_scalar(node)
        filename = pathlib.Path(os.path.expandvars(filename))
        filename = filename.expanduser()

        with filename.open(encoding="UTF-8") as f:
            return yaml.load(f, IncludeLoader)  # noqa: S506 as IncludeLoader extends yaml.SafeLoader


IncludeLoader.add_constructor("!include", IncludeLoader.include)
