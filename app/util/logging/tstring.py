# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging
import functools

from ..helpers.tstring import tstring_as_fstring
from string.templatelib import Template


logging_logrecord_getMessage = logging.LogRecord.getMessage

@functools.wraps(logging.LogRecord.getMessage)
def getMessage(self) -> str:
    msg = self.msg
    if isinstance(msg, Template):
        return tstring_as_fstring(msg)
    else:
        return logging_logrecord_getMessage(self)

logging.LogRecord.getMessage = getMessage