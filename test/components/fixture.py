# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro


import pytest
import re

from typing import Any, Generator

from app.components import BaseComponentConfig, ComponentBase


# MARK: Component configuration fixture
class ComponentConfigFixture[T: BaseComponentConfig]:
    def __init__(self):
        pass

    def create(self, data: dict[str, Any], cls : type[T]) -> T:
        self.config = cls.model_validate(data)
        return self.config

    def get(self) -> T:
        if not hasattr(self, 'config'):
            raise RuntimeError("Configuration not initialized. Call 'create()' first.")
        return self.config


@pytest.fixture(scope='function')
def component_config() -> Generator[ComponentConfigFixture]:
    yield ComponentConfigFixture()



# MARK: Component fixture
class ComponentFixture[T: ComponentBase]:
    def __init__(self):
        pass

    def create(self, data: dict[str, Any], cls : type[T]) -> T:
        self.config = cls.config_class.model_validate(data)
        self.component = cls(config=self.config)
        return self.component

    def get(self) -> T:
        if self.component is None:
            raise RuntimeError("Component not initialized. Call 'create()' first.")
        return self.component


@pytest.fixture(scope='function')
def component() -> Generator[ComponentFixture]:
    yield ComponentFixture()