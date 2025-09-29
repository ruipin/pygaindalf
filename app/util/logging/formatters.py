# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging

from typing import override


class ConditionalFormatter(logging.Formatter):
    @override
    def format(self, record: logging.LogRecord) -> str:
        simple = getattr(record, "simple", False)
        if simple:
            return record.getMessage()
        else:
            return super().format(record)
