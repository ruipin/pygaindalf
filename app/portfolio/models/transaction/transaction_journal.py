# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from ...journal.journal import Journal
from .transaction_impl import TransactionImpl


class TransactionJournal(
    TransactionImpl,
    Journal,
    init=False,
):
    pass
