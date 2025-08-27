# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging

from typing import override

# TODO: Once Python 3.14 is the minimum, we should add t-string support to the default formatter
#       and convert all our logging calls to use t-strings instead of f-strings.
#       See https://peps.python.org/pep-0750/#approach-2-custom-formatters

class ConditionalFormatter(logging.Formatter):
    @override
    def format(self, record):
        simple = getattr(record, 'simple', False)
        if simple:
            return record.getMessage()
        else:
            return logging.Formatter.format(self, record)
