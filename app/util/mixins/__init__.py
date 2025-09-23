# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import re
def shorten_name(input : str) -> str:
    # Assume camelcase
    res = re.sub('[^A-Z0-9]', '', input)
    if res:
        return res

    # Otherwise, do nothing
    return input


# Import mixins
from .named import *
from .hierarchical import *
from .loggable import *

# Create short-hands
class HierarchicalNamedMixin(HierarchicalMixin, NamedMixin):
    """
    Mixin combining hierarchy and naming support.
    """
    pass

class LoggableHierarchicalMixin(LoggableMixin, HierarchicalMixin):
    """
    Mixin combining logging and hierarchy support.
    """
    pass

class LoggableNamedMixin(LoggableMixin, NamedMixin):
    """
    Mixin combining logging and naming support.
    """
    pass

class LoggableHierarchicalNamedMixin(LoggableMixin, HierarchicalMixin, NamedMixin):
    """
    Mixin combining logging, hierarchy, and naming support.
    """
    pass