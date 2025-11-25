# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import MutableSet
from typing import TYPE_CHECKING, override

from ...collections import OrderedViewMutableSet
from ...journal.journal import Journal
from ..transaction import Transaction, TransactionRecord
from .ledger_impl import LedgerImpl


if TYPE_CHECKING:
    from ....util.models.uid import Uid


class LedgerJournal(
    LedgerImpl[OrderedViewMutableSet[Transaction]],
    Journal,
    MutableSet[Transaction],
    init=False,
):
    # MARK: MutableSet ABC
    @override
    def add(self, value: Transaction | TransactionRecord | Uid) -> None:
        self.transactions.add(Transaction.narrow_to_instance(value))

    @override
    def discard(self, value: Transaction | TransactionRecord | Uid) -> None:
        self.transactions.discard(Transaction.narrow_to_instance(value))
