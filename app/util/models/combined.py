# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import ClassVar

from pydantic import Field

from ..mixins import LoggableMixin
from .hierarchical import HierarchicalModel
from .hierarchical_root import HierarchicalRootModel
from .single_initialization import SingleInitializationModel


# Loggable + Single Initialization
class LoggableModel(LoggableMixin, SingleInitializationModel):
    pass


# Hierarchical + Named
class HierarchicalNamedModel(HierarchicalModel):
    PROPAGATE_INSTANCE_NAME_FROM_PARENT: ClassVar[bool] = True
    PROPAGATE_INSTANCE_NAME_TO_CHILDREN: ClassVar[bool] = True

    instance_name: str | None = Field(default=None, min_length=1, description="Name of the instance.")


class HierarchicalRootNamedModel(HierarchicalRootModel):
    PROPAGATE_INSTANCE_NAME_FROM_PARENT: ClassVar[bool] = True
    PROPAGATE_INSTANCE_NAME_TO_CHILDREN: ClassVar[bool] = True

    instance_name: str | None = Field(default=None, min_length=1, description="Name of the instance.")


# Loggable + Hierarchical
class LoggableHierarchicalRootModel(LoggableMixin, HierarchicalRootModel):
    pass


class LoggableHierarchicalModel(LoggableMixin, HierarchicalModel):
    pass


# Loggable + Hierarchical + Named
class LoggableHierarchicalRootNamedModel(LoggableMixin, HierarchicalRootNamedModel):
    pass


class LoggableHierarchicalNamedModel(LoggableMixin, HierarchicalNamedModel):
    pass
