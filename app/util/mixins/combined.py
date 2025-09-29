# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from .hierarchical import HierarchicalMixin
from .loggable import LoggableMixin
from .named import NamedMixin


class HierarchicalNamedMixin(HierarchicalMixin, NamedMixin):
    """Mixin combining hierarchy and naming support."""


class LoggableHierarchicalMixin(LoggableMixin, HierarchicalMixin):
    """Mixin combining logging and hierarchy support."""


class LoggableNamedMixin(LoggableMixin, NamedMixin):
    """Mixin combining logging and naming support."""


class LoggableHierarchicalNamedMixin(LoggableMixin, HierarchicalMixin, NamedMixin):
    """Mixin combining logging, hierarchy, and naming support."""
