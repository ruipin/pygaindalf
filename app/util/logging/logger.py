# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools
import logging
import re

from typing import Any, override

from .loggable_protocol import LoggableProtocol


class Logger(logging.Logger):
    @override
    def isEnabledFor(self, level: int, *, handler: str | None = None) -> bool:
        if handler is not None:
            if handler == "tty":
                return self.isEnabledForTty(level)
            elif handler == "file":
                return self.isEnabledForFile(level)
            else:
                msg = f"Unknown handler: {handler}. Expected 'tty' or 'file'."
                raise ValueError(msg)
        else:
            return super().isEnabledFor(level)

    def isEnabledForTty(self, level: int) -> bool:  # noqa: N802 which matches isEnabledFor
        from .manager import LoggingManager

        ch = LoggingManager().ch
        if ch is None or ch.level > level:
            return False
        return super().isEnabledFor(level)

    def isEnabledForFile(self, level: int) -> bool:  # noqa: N802 which matches isEnabledFor
        from .manager import LoggingManager

        fh = LoggingManager().fh
        if fh is None or fh.level > level:
            return False
        return super().isEnabledFor(level)


logging.setLoggerClass(Logger)


# Helper for class constructors to obtain a logger object
# Returns a logger object
original_logging_getLogger = logging.getLogger  # noqa: N816


def _getLogger(obj: object, parent: Any = None, name: str | None = None) -> logging.Logger:  # noqa: N802
    # Determine the logger name
    if name is None:
        if isinstance(obj, str):
            name = obj
        else:
            cls_name = type(obj).__name__
            if isinstance(cls_name, str):
                name = cls_name
            else:
                msg = f"Cannot determine logger name from object: {obj}"
                raise TypeError(msg)

    # Create or get the logger
    logger = None
    if parent is None or not isinstance(parent, LoggableProtocol):
        logger = original_logging_getLogger(name)
    elif isinstance(parent, logging.Logger):
        logger = parent.getChild(name)
    else:
        logger = parent.log.getChild(name)

    # Try to apply the logging level from the manager
    from .manager import LoggingManager

    manager = LoggingManager()
    if manager.initialized:
        manager.apply_logging_level(logger)

    # Done
    return logger


def getLogger(obj: object, parent: Any = None, name: str | None = None) -> Logger:
    logger = _getLogger(obj, parent=parent, name=name)

    if not isinstance(logger, Logger):
        msg = f"Expected a Logger instance, got: {type(logger)}"
        raise TypeError(msg)

    return logger


@functools.wraps(logging.getLogger)
def logging_getLogger_wrapper(name: str | None = None) -> logging.Logger:  # noqa: N802
    if name is None:
        return logging.root
    else:
        return _getLogger(name)


logging.getLogger = logging_getLogger_wrapper
