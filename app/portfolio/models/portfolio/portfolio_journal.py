# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from functools import cached_property

from typing import TYPE_CHECKING, override, Iterator
from collections.abc import MutableSet

from ...journal.entity_journal import EntityJournal

from ...util.uid import Uid
from ...collections import OrderedViewUidMutableSet, UidProxyOrderedViewMutableSet
from ..ledger import Ledger
from .portfolio_base import PortfolioBase


class PortfolioJournal(
    PortfolioBase[OrderedViewUidMutableSet[Ledger],
    UidProxyOrderedViewMutableSet[Ledger]],
    EntityJournal,
    MutableSet[Ledger],
    init=False
):

    # MARK: MutableSet ABC
    @override
    def add(self, value : Ledger | Uid) -> None:
        self.ledger_uids.add(Ledger.narrow_to_uid(value))

    @override
    def discard(self, value : Ledger | Uid) -> None:
        self.ledger_uids.discard(Ledger.narrow_to_uid(value))