# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging

from typing import override


class HandlerFilter(logging.Filter):
    def __init__(self, handler_name: str):
        super().__init__()
        self.handler_name = handler_name

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        record_handler = getattr(record, 'handler', None)
        return record_handler is None or record_handler == self.handler_name