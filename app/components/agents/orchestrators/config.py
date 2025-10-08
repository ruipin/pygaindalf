# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from collections.abc import Sequence
from typing import override

from ..base import BaseAgent, BaseAgentConfig
from .base import BaseOrchestrator, BaseOrchestratorConfig


# MARK: Configuration
class ConfigOrchestratorConfig(BaseOrchestratorConfig):
    components: Sequence[BaseAgentConfig]


# MARK: Orchestrator
class ConfigOrchestrator(BaseOrchestrator[ConfigOrchestratorConfig]):
    @override
    def _do_run(self) -> None:
        for i, component_config in enumerate(self.config.components):
            title = f"{i}.{component_config.title}"
            component = component_config.create_component(instance_name=title, instance_parent=self)
            assert isinstance(component, BaseAgent)
            with self.subcontext():
                component.run(self.subcontext)


COMPONENT = ConfigOrchestrator
