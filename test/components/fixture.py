# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import Any

import pytest

from app.components import BaseComponent, BaseComponentConfig
from app.runtime import Runtime

from ..util.config.fixture import ConfigFixture


# MARK: Component configuration fixture
class ComponentConfigFixture[T: BaseComponentConfig]:
    def __init__(self):
        self.config: T | None = None

    def create(self, data: dict[str, Any], cls: type[T]) -> T:
        self.config = cls.model_validate(data)
        return self.config

    def get(self) -> T:
        if self.config is None:
            raise RuntimeError("Configuration not initialized. Call 'create()' first.")
        return self.config


@pytest.fixture
def component_config() -> ComponentConfigFixture:
    return ComponentConfigFixture()


# MARK: Component fixture
class ComponentFixture[T: BaseComponent]:
    def __init__(self):
        self.config: BaseComponentConfig | None = None
        self.component: T | None = None

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


# MARK: Runtime
class RuntimeFixture:
    def __init__(self, config: ConfigFixture):
        self.config = config
        self.runtime: Runtime | None = None

    def create(self, data: dict[str, Any]) -> Runtime:
        self.config.create(data)
        self.runtime = Runtime(config=self.config.get())
        self.runtime.initialize()
        return self.runtime

    def get(self) -> Runtime:
        if self.runtime is None:
            raise RuntimeError("Runtime not initialized.")
        return self.runtime


@pytest.fixture
def runtime(config: ConfigFixture) -> RuntimeFixture:
    return RuntimeFixture(config)
