# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest
from decimal import Decimal

from typing import override

from app.components.component import (
    BaseComponentConfig,
    ComponentBase,
    ComponentField,
    component_entrypoint,
)


# Dummy component and config for testing entrypoint behavior
class DummyComponentConfig(BaseComponentConfig):
    @classmethod
    @override
    def get_component_class_for_package(cls, package) -> type[ComponentBase]:
        return DummyComponent


class DummyComponent(ComponentBase):
    config = ComponentField(DummyComponentConfig)

    def __init__(self, config: DummyComponentConfig):
        super().__init__(config)
        self.events: list[str] = []

    @override
    def before_entrypoint(self, entrypoint_name: str, *args, **kwargs) -> None:
        super().before_entrypoint(entrypoint_name, *args, **kwargs)
        # inside_entrypoint should already be True here
        assert self.inside_entrypoint is True
        self.events.append(f"before:{entrypoint_name}")

    @override
    def wrap_entrypoint(self, entrypoint, *args, **kwargs):
        # We record around the super call which applies the Decimal context
        self.events.append(f"wrap:{entrypoint.__name__}:before")
        result = super().wrap_entrypoint(entrypoint, *args, **kwargs)
        self.events.append(f"wrap:{entrypoint.__name__}:after")
        return result

    @override
    def after_entrypoint(self, entrypoint_name: str) -> None:
        # Still inside the entrypoint here
        assert self.inside_entrypoint is True
        self.events.append(f"after:{entrypoint_name}")
        super().after_entrypoint(entrypoint_name)

    # Non-entrypoint helper
    def helper(self) -> Decimal:
        # Uses the component's Decimal context
        return self.decimal('1') / self.decimal('3')

    @component_entrypoint
    def compute(self) -> Decimal:
        return self.helper()


@pytest.fixture(scope='function')
def dummy_component():
    # Configure precision and relax traps to avoid Inexact exceptions
    cfg = DummyComponentConfig.model_validate(
        {
            'package': 'dummy',
            'decimal': {
                'precision': 4,
                'rounding': 'HALF_UP',
                'traps': {
                    'INEXACT': False,
                    'ROUNDED': False,
                },
            },
        },
        context={'concrete_class': DummyComponentConfig},
    )
    yield DummyComponent(cfg)


@pytest.mark.components
class TestComponentEntrypoint:
    def test_non_entrypoint_method_raises_when_called_directly(self, dummy_component):
        with pytest.raises(RuntimeError) as ei:
            dummy_component.helper()
        assert "not a component entrypoint" in str(ei.value)

    def test_entrypoint_applies_decimal_context_and_calls_hooks(self, dummy_component):
        # Compute inside entrypoint; with precision=4 we expect "0.3333"
        result = dummy_component.compute()
        assert isinstance(result, Decimal)
        assert str(result) == '0.3333'

        # Hooks should have been called in order while inside_entrypoint
        assert dummy_component.events == [
            'before:compute',
            'wrap:compute:before',
            'wrap:compute:after',
            'after:compute',
        ]

        # After the entrypoint completes, we're no longer inside an entrypoint
        assert dummy_component.inside_entrypoint is False
