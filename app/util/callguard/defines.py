# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro


# MARK: Configuration
CALLGUARD_ENABLED = __debug__ # Global enable/disable switch
CALLGUARD_GETATTR_SETATTR_ENABLED = True # Enable/disable the use of __getattribute__ and __setattr__
CALLGUARD_SELF_IS_FIRST_ARGUMENT = True # Whether to assume the first argument is 'self' or 'cls' (if False, will use introspection to find the first argument)
CALLGUARD_STRICT_SELF = True # Whether to enforce that the first argument is named 'self' or 'cls'


# MARK: Logger
from ..logging import getLogger
LOG = getLogger(__name__)
LOG.disabled = True