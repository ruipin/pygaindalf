# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging

from typing import Any, override

from .loggable_protocol import LoggableProtocol


class Logger(logging.Logger):
    @override
    def isEnabledFor(self, level: int, *, handler : str|None = None) -> bool:
        if handler is not None:
            if handler == 'tty':
                return self.isEnabledForTty(level)
            elif handler == 'file':
                return self.isEnabledForFile(level)
            else:
                raise ValueError(f"Unknown handler: {handler}. Expected 'tty' or 'file'.")
        else:
            return super().isEnabledFor(level)

    def isEnabledForTty(self, level: int) -> bool:
        from .manager import LoggingManager
        ch = LoggingManager().ch
        if ch is None or ch.level > level:
            return False
        return super().isEnabledFor(level)

    def isEnabledForFile(self, level: int) -> bool:
        from .manager import LoggingManager
        fh = LoggingManager().fh
        if fh is None or fh.level > level:
            return False
        return super().isEnabledFor(level)

logging.setLoggerClass(Logger)


# Helper for class constructors to obtain a logger object
# Returns a logger object
def getLogger(obj, parent:Any=None, name:str|None=None) -> Logger:
    if name is None:
        if isinstance(obj, str):
            name = obj
        else:
            cls_name = type(obj).__name__
            if isinstance(cls_name, str):
                name = cls_name
            else:
                raise TypeError("Cannot determine logger name from object: {}".format(obj))

    logger = None
    if parent is None or not isinstance(parent, LoggableProtocol):
        logger = logging.getLogger(name)
    elif isinstance(parent, logging.Logger):
        logger = parent.getChild(name)
    else:
        logger = parent.log.getChild(name)

    if not isinstance(logger, Logger):
        raise TypeError("Expected a Logger instance, got: {}".format(type(logger)))
    return logger