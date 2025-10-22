# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta

from .... import Agent, AgentConfig


# MARK: Importer Base Configuration
class ImporterConfig(AgentConfig, metaclass=ABCMeta):
    pass


# MARK: Importer Base class
class Importer[C: ImporterConfig](Agent[C], metaclass=ABCMeta):
    pass
