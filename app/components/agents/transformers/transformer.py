# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta

from .. import Agent, AgentConfig


# MARK: Transformer Base Configuration
class TransformerConfig(AgentConfig, metaclass=ABCMeta):
    pass


# MARK: Transformer Base class
class Transformer[C: TransformerConfig](Agent[C], metaclass=ABCMeta):
    pass
