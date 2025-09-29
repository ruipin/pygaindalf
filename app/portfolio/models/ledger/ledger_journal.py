# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import MutableSet
from typing import TYPE_CHECKING, override

from ...collections import OrderedViewUidMutableSet, UidProxyOrderedViewMutableSet
from ...journal.entity_journal import EntityJournal
from ..transaction import Transaction
from .ledger_base import LedgerBase


if TYPE_CHECKING:
    from ...util.uid import Uid


class LedgerJournal(
    LedgerBase[OrderedViewUidMutableSet[Transaction], UidProxyOrderedViewMutableSet[Transaction]],
    EntityJournal,
    MutableSet[Transaction],
    init=False,
):
    # MARK: MutableSet ABC
    @override
    def add(self, value: Transaction | Uid) -> None:
        self.transaction_uids.add(Transaction.narrow_to_uid(value))

    @override
    def discard(self, value: Transaction | Uid) -> None:
        self.transaction_uids.discard(Transaction.narrow_to_uid(value))
