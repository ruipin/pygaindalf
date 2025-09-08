# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from functools import cached_property

from typing import TYPE_CHECKING, override, Iterator
from collections.abc import MutableSet

from ...journal.entity_journal import EntityJournal

from ..uid import Uid
from ..ledger import Ledger, OrderedViewLedgerUidSet, UidProxyOrderedViewLedgerSet

from .portfolio_base import PortfolioBase


class PortfolioJournal(PortfolioBase[OrderedViewLedgerUidSet, UidProxyOrderedViewLedgerSet], EntityJournal, MutableSet[Ledger], init=False):
    if TYPE_CHECKING:
        pass


    # MARK: Ledgers
    @cached_property
    def ledgers(self) -> UidProxyOrderedViewLedgerSet:
        return UidProxyOrderedViewLedgerSet(owner=self, field='ledger_uids')


    # MARK: MutableSet ABC
    @override
    def add(self, value : Ledger | Uid) -> None:
        self.ledger_uids.add(Ledger.narrow_to_uid(value))

    @override
    def discard(self, value : Ledger | Uid) -> None:
        self.ledger_uids.discard(Ledger.narrow_to_uid(value))