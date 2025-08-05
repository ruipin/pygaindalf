# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta, abstractmethod

from .. import ProviderBase, ProviderBaseConfig, ComponentField


# MARK: Provider Base Configuration
class ForexProviderBaseConfig(ProviderBaseConfig, metaclass=ABCMeta):
    pass



# MARK: Provider Base class
class ForexProviderBase(ProviderBase, metaclass=ABCMeta):
    config = ComponentField(ForexProviderBaseConfig)