# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import yaml
import os

from io import IOBase
from typing import runtime_checkable, Protocol



@runtime_checkable
class NamedProtocol(Protocol):
    @property
    def name(self) -> str: ...


class IncludeLoader(yaml.SafeLoader):
    def __init__(self, stream : IOBase, root : str|None = None):
        if root is None:
            if isinstance(stream, NamedProtocol):
                root = os.path.dirname(os.path.abspath(stream.name))
            else:
                root = os.getcwd()

        self._root : str = root

        super(IncludeLoader, self).__init__(stream)

    def include(self, node):
        filename = os.path.join(self._root, self.construct_scalar(node))

        with open(filename, 'r', encoding='UTF-8') as f:
            return yaml.load(f, IncludeLoader)

IncludeLoader.add_constructor('!include', IncludeLoader.include)