# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging
from typing import runtime_checkable, Protocol, Any

#############
@runtime_checkable
class LoggableProtocol(Protocol):
    @property
    def log(self) -> logging.Logger: ...