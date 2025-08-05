# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override
from abc import ABCMeta

from ...util import classproperty
from .. import ComponentBaseConfig, ComponentBase, ComponentField


# MARK: Provider Base Configuration
class ProviderBaseConfig(ComponentBaseConfig, metaclass=ABCMeta):
    @classproperty
    @override
    def package_root(cls) -> str:
        return 'app.components.providers'



# MARK: Provider Base class
class ProviderBase(ComponentBase, metaclass=ABCMeta):
    config = ComponentField(ProviderBaseConfig)