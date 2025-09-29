# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools
import logging

from string.templatelib import Template

from ..helpers.tstring import tstring_as_fstring


logging_logrecord_getMessage = logging.LogRecord.getMessage  # noqa: N816 matches logging.LogRecord.getMessage


@functools.wraps(logging.LogRecord.getMessage)
def getMessage(self: logging.LogRecord) -> str:  # noqa: N802 matches logging.LogRecord.getMessage
    msg = self.msg
    if isinstance(msg, Template):
        return tstring_as_fstring(msg)
    else:
        return logging_logrecord_getMessage(self)


logging.LogRecord.getMessage = getMessage
