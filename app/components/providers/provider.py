# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from typing import override

from ...util.helpers import classproperty
from .. import BaseComponentConfig, ComponentBase


# MARK: Provider Base Configuration
class BaseProviderConfig(BaseComponentConfig, metaclass=ABCMeta):
    @classproperty
    @override
    def package_root(cls) -> str:
        return "app.components.providers"


# MARK: Provider Base class
class ProviderBase[C: BaseProviderConfig](ComponentBase[C], metaclass=ABCMeta):
    pass
