# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import Any

import pytest

from app.components import BaseComponentConfig, ComponentBase


# MARK: Component configuration fixture
class ComponentConfigFixture[T: BaseComponentConfig]:
    def __init__(self):
        pass

    def create(self, data: dict[str, Any], cls: type[T]) -> T:
        self.config = cls.model_validate(data)
        return self.config

    def get(self) -> T:
        if not hasattr(self, "config"):
            raise RuntimeError("Configuration not initialized. Call 'create()' first.")
        return self.config


@pytest.fixture
def component_config() -> ComponentConfigFixture:
    return ComponentConfigFixture()


# MARK: Component fixture
class ComponentFixture[T: ComponentBase]:
    def __init__(self):
        pass

    def create(self, data: dict[str, Any], cls: type[T]) -> T:
        self.config = cls.config_class.model_validate(data)
        self.component = cls(config=self.config)
        return self.component

    def get(self) -> T:
        if self.component is None:
            raise RuntimeError("Component not initialized. Call 'create()' first.")
        return self.component


@pytest.fixture
def component() -> ComponentFixture:
    return ComponentFixture()
