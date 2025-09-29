# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol, runtime_checkable


if TYPE_CHECKING:
    import logging


#############
@runtime_checkable
class LoggableProtocol(Protocol):
    @property
    @abstractmethod
    def log(self) -> logging.Logger:
        msg = "Subclasses must implement log property"
        raise NotImplementedError(msg)
