# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from decimal import Decimal
from typing import override

import pytest

from app.components.agents.agent import Agent, AgentConfig
from app.components.component import component_entrypoint
from app.context import SubContext

from .fixture import RuntimeFixture


# Dummy component and config for testing entrypoint behavior
class DummyAgentConfig(AgentConfig):
    @classmethod
    @override
    def get_component_class_for_package(cls, package) -> type[Agent]:
        return DummyAgent


class DummyAgent(Agent[DummyAgentConfig]):
    def __init__(self, config: DummyAgentConfig, *, instance_parent=None, instance_name: str | None = None):
        super().__init__(config, instance_parent=instance_parent, instance_name=instance_name)
        self.events: list[str] = []

    @override
    def _before_entrypoint(self, entrypoint_name: str, *args, **kwargs) -> None:
        super()._before_entrypoint(entrypoint_name, *args, **kwargs)
        # inside_entrypoint should already be True here
        assert self.inside_entrypoint is True
        self.events.append(f"before:{entrypoint_name}")

    @override
    def _wrap_entrypoint(self, entrypoint, *args, **kwargs):
        # We record around the super call which applies the Decimal context
        self.events.append(f"wrap:{entrypoint.__name__}:before")
        result = super()._wrap_entrypoint(entrypoint, *args, **kwargs)
        self.events.append(f"wrap:{entrypoint.__name__}:after")
        return result

    @override
    def _after_entrypoint(self, entrypoint_name: str) -> None:
        # Still inside the entrypoint here
        assert self.inside_entrypoint is True
        self.events.append(f"after:{entrypoint_name}")
        super()._after_entrypoint(entrypoint_name)

    # Non-entrypoint helper
    def helper(self) -> Decimal:
        # Uses the component's Decimal context
        return self.decimal("1") / self.decimal("3")

    @component_entrypoint
    def compute(self) -> Decimal:
        return self.helper()


@pytest.fixture
def dummy_agent(runtime: RuntimeFixture) -> DummyAgent:
    runtime_instance = runtime.create({})

    cfg = DummyAgentConfig.model_validate(
        {
            "package": "dummy",
            "context": {
                "decimal": {
                    "precision": 4,
                    "rounding": "HALF_UP",
                    "traps": {
                        "INEXACT": False,
                        "ROUNDED": False,
                    },
                },
            },
        },
        context={"concrete_class": DummyAgentConfig},
    )

    return DummyAgent(cfg, instance_parent=runtime_instance, instance_name="dummy-agent")


@pytest.mark.components
@pytest.mark.agents
class TestComponentEntrypoint:
    def test_non_entrypoint_method_raises_when_called_directly(self, dummy_agent: DummyAgent):
        with pytest.raises(RuntimeError) as ei:
            dummy_agent.helper()
        assert "not a component entrypoint" in str(ei.value)

    def test_entrypoint_applies_decimal_context_and_calls_hooks(self, runtime: RuntimeFixture, dummy_agent: DummyAgent):
        agent = dummy_agent

        root_context = runtime.get().context
        agent_context = SubContext(parent=root_context, config=agent.config.context)

        with root_context, agent_context:
            # Compute inside entrypoint; with precision=4 we expect "0.3333"
            result = agent.compute()

        assert isinstance(result, Decimal)
        assert str(result) == "0.3333"

        # Hooks should have been called in order while inside_entrypoint
        assert agent.events == [
            "before:compute",
            "wrap:compute:before",
            "wrap:compute:after",
            "after:compute",
        ]

        # After the entrypoint completes, we're no longer inside an entrypoint
        assert agent.inside_entrypoint is False
