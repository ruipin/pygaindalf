# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from collections.abc import Sequence
from typing import override

from ..agent import Agent, AgentConfig
from .orchestrator import Orchestrator, OrchestratorConfig


# MARK: Configuration
class ConfigOrchestratorConfig(OrchestratorConfig):
    components: Sequence[AgentConfig]


# MARK: Orchestrator
class ConfigOrchestrator(Orchestrator[ConfigOrchestratorConfig]):
    @override
    def _do_run(self) -> None:
        for i, component_config in enumerate(self.config.components):
            title = f"{i}.{component_config.title}"
            component = component_config.create_component(instance_name=title, instance_parent=self)
            assert isinstance(component, Agent)
            with self._create_subcontext(config=component_config.context) as subctx:
                component.run(subctx)


COMPONENT = ConfigOrchestrator
