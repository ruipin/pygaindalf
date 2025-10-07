# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import override

from pydantic import Field

from .base import BaseAgent, BaseAgentConfig


# MARK: Configuration
class HelloWorldAgentConfig(BaseAgentConfig):
    message: str = Field(default="Hello, World!", description="The message to print")


# MARK: Orchestrator
class HelloWorldAgent(BaseAgent[HelloWorldAgentConfig]):
    @override
    def _do_run(self) -> None:
        self.log.info(self.config.message)


COMPONENT = HelloWorldAgent
