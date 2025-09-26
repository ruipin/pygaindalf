# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from functools import cached_property

from typing import TYPE_CHECKING, override, Iterator, Generic
from collections.abc import MutableSet

from ...journal.entity_journal import EntityJournal

from ..uid import Uid
from ..transaction import Transaction, OrderedViewTransactionUidSet, UidProxyOrderedViewTransactionSet

from .ledger_base import LedgerBase


class LedgerJournal(LedgerBase[OrderedViewTransactionUidSet, UidProxyOrderedViewTransactionSet], EntityJournal, MutableSet[Transaction], init=False):
    # MARK: MutableSet ABC
    @override
    def add(self, value : Transaction | Uid) -> None:
        self.transaction_uids.add(Transaction.narrow_to_uid(value))

    @override
    def discard(self, value : Transaction | Uid) -> None:
        self.transaction_uids.discard(Transaction.narrow_to_uid(value))