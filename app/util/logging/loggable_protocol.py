# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging
from typing import runtime_checkable, Protocol, Any
from abc import abstractmethod

#############
@runtime_checkable
class LoggableProtocol(Protocol):
    @property
    @abstractmethod
    def log(self) -> logging.Logger:
        raise NotImplementedError("Subclasses must implement log property")