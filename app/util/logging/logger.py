# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging

from typing import Any

from .loggable_protocol import LoggableProtocol


# Helper for class constructors to obtain a logger object
# Returns a logger object
def getLogger(obj, parent:Any=None, name:str|None=None) -> logging.Logger:
    if name is None:
        if isinstance(obj, str):
            name = obj
        else:
            cls_name = obj.__class__.__name__
            if isinstance(cls_name, str):
                name = cls_name
            else:
                raise TypeError("Cannot determine logger name from object: {}".format(obj))

    if parent is None or not isinstance(parent, LoggableProtocol):
        return logging.getLogger(name)
    elif isinstance(parent, logging.Logger):
        return parent.getChild(name)
    else:
        return parent.log.getChild(name)