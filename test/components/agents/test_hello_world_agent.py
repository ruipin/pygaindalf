# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest

from ..fixture import RuntimeFixture


@pytest.mark.components
@pytest.mark.agents
@pytest.mark.runtime
def test_hello_world_agent_logs_configured_message(runtime: RuntimeFixture, caplog: pytest.LogCaptureFixture) -> None:
    message = "Hello from the runtime fixture test"

    runtime_instance = runtime.create(
        {
            "components": [
                {
                    "package": "hello_world",
                    "title": "hello-world",
                    "message": message,
                }
            ],
        }
    )

    with caplog.at_level("INFO"):
        runtime_instance.run()

    hello_world_logs = [record.getMessage() for record in caplog.records if record.levelname == "INFO"]

    assert message in hello_world_logs


@pytest.mark.components
@pytest.mark.agents
@pytest.mark.runtime
def test_multiple_hello_world_agents_log_their_messages(runtime: RuntimeFixture, caplog: pytest.LogCaptureFixture) -> None:
    messages = [
        "First agent reporting in",
        "Second agent says hi",
    ]

    runtime_instance = runtime.create(
        {
            "components": [
                {
                    "package": "hello_world",
                    "title": "first-agent",
                    "message": messages[0],
                },
                {
                    "package": "hello_world",
                    "title": "second-agent",
                    "message": messages[1],
                },
            ],
        }
    )

    with caplog.at_level("INFO"):
        runtime_instance.run()

    observed = [record.getMessage() for record in caplog.records if record.levelname == "INFO"]

    for expected_message in messages:
        assert expected_message in observed


@pytest.mark.components
@pytest.mark.agents
@pytest.mark.runtime
@pytest.mark.orchestrators
def test_sub_orchestrator_runs_hello_world_agent(runtime: RuntimeFixture, caplog: pytest.LogCaptureFixture) -> None:
    message = "Nested hello world message"

    runtime_instance = runtime.create(
        {
            "components": [
                {
                    "package": "orchestrators.config_orchestrator",
                    "title": "sub-orchestrator",
                    "components": [
                        {
                            "package": "hello_world",
                            "title": "nested-hello",
                            "message": message,
                        }
                    ],
                }
            ],
        }
    )

    with caplog.at_level("INFO"):
        runtime_instance.run()

    nested_logs = [record.getMessage() for record in caplog.records if record.levelname == "INFO"]

    assert message in nested_logs
