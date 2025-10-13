# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta

from .. import Agent, AgentConfig


# MARK: Exporter Base Configuration
class ExporterConfig(AgentConfig, metaclass=ABCMeta):
    pass


# MARK: Exporter Base class
class Exporter[C: ExporterConfig](Agent[C], metaclass=ABCMeta):
    pass
