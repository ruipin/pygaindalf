# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from typing import TYPE_CHECKING

from ....context import SubContext
from .. import Agent, AgentConfig


if TYPE_CHECKING:
    from ....context import ContextConfig


# MARK: Orchestrator Base Configuration
class OrchestratorConfig(AgentConfig, metaclass=ABCMeta):
    pass


# MARK: Orchestrator Base class
class Orchestrator[C: OrchestratorConfig](Agent[C], metaclass=ABCMeta):
    def _create_subcontext(self, *, config: ContextConfig | None = None) -> SubContext:
        return SubContext(parent=self.context, config=config or self.config.context)
