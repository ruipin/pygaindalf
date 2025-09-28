# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override
from collections.abc import MutableSet

from ...journal.entity_journal import EntityJournal
from ...collections import OrderedViewUidMutableSet, UidProxyOrderedViewMutableSet

from ...util.uid import Uid
from ..transaction import Transaction

from .ledger_base import LedgerBase


class LedgerJournal(
    LedgerBase[OrderedViewUidMutableSet[Transaction], UidProxyOrderedViewMutableSet[Transaction]],
    EntityJournal,
    MutableSet[Transaction],
    init=False
):

    # MARK: MutableSet ABC
    @override
    def add(self, value : Transaction | Uid) -> None:
        self.transaction_uids.add(Transaction.narrow_to_uid(value))

    @override
    def discard(self, value : Transaction | Uid) -> None:
        self.transaction_uids.discard(Transaction.narrow_to_uid(value))