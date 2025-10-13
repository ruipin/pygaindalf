# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import override

from pydantic import Field

from .agent import Agent, AgentConfig


# MARK: Configuration
class HelloWorldAgentConfig(AgentConfig):
    message: str = Field(default="Hello, World!", description="The message to print")


# MARK: Orchestrator
class HelloWorldAgent(Agent[HelloWorldAgentConfig]):
    @override
    def _do_run(self) -> None:
        self.log.info(self.config.message)


COMPONENT = HelloWorldAgent
