# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from typing import override

from ....runtime.context import BaseContext, SubContext
from .. import BaseAgent, BaseAgentConfig


# MARK: Orchestrator Base Configuration
class BaseOrchestratorConfig(BaseAgentConfig, metaclass=ABCMeta):
    pass


# MARK: Orchestrator Base class
class BaseOrchestrator[C: BaseOrchestratorConfig](BaseAgent[C], metaclass=ABCMeta):
    context: BaseContext

    def _create_subcontext(self) -> None:
        self.subcontext = SubContext(self.context)

    @override
    def _pre_run(self) -> None:
        self._create_subcontext()
