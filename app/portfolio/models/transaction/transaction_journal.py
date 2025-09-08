# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime

from typing import TYPE_CHECKING
from decimal import Decimal

from ...journal.entity_journal import EntityJournal

from .transaction_type import TransactionType


class TransactionJournal(EntityJournal, init=False):
    if TYPE_CHECKING:
        type           : TransactionType
        date           : datetime.date
        quantity       : Decimal
        consideration  : Decimal
        fees           : Decimal