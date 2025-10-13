# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from typing import override

from ...util.helpers import classproperty
from ..component import Component, ComponentConfig


# MARK: Provider Base Configuration
class ProviderConfig(ComponentConfig, metaclass=ABCMeta):
    @classproperty
    @override
    def package_root(cls) -> str:
        return "app.components.providers"


# MARK: Provider Base class
class Provider[C: ProviderConfig](Component[C], metaclass=ABCMeta):
    @classproperty
    def default_key(cls) -> str:
        msg = "Subclasses must implement the 'default_key' class property."
        raise NotImplementedError(msg)
