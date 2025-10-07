# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Any, ClassVar, Self, override

from pydantic import ModelWrapValidatorHandler, model_validator

from ..components.agents.orchestrators import ConfigOrchestrator, ConfigOrchestratorConfig


# MARK: Configuration
class RuntimeOrchestratorConfig(ConfigOrchestratorConfig):
    PROPAGATE_TO_CHILDREN: ClassVar[bool] = False  # Do not propagate package to children

    @model_validator(mode="wrap")
    @classmethod
    @override
    def _coerce_to_concrete_class(cls, data: Any, handler: ModelWrapValidatorHandler) -> Self:
        return handler(data)


# MARK: Orchestrator
class RuntimeOrchestrator(ConfigOrchestrator):
    pass


COMPONENT = RuntimeOrchestrator
