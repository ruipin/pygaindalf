# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta

from .. import BaseAgent, BaseAgentConfig


# MARK: Importer Base Configuration
class BaseImporterConfig(BaseAgentConfig, metaclass=ABCMeta):
    pass


# MARK: Importer Base class
class BaseImporter[C: BaseImporterConfig](BaseAgent[C], metaclass=ABCMeta):
    pass
