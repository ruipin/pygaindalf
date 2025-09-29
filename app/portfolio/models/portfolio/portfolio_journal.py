# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import MutableSet
from typing import TYPE_CHECKING, override

from ...collections import OrderedViewUidMutableSet, UidProxyOrderedViewMutableSet
from ...journal.entity_journal import EntityJournal
from ..ledger import Ledger
from .portfolio_base import PortfolioBase


if TYPE_CHECKING:
    from ...util.uid import Uid


class PortfolioJournal(
    PortfolioBase[OrderedViewUidMutableSet[Ledger], UidProxyOrderedViewMutableSet[Ledger]],
    EntityJournal,
    MutableSet[Ledger],
    init=False,
):
    # MARK: MutableSet ABC
    @override
    def add(self, value: Ledger | Uid) -> None:
        self.ledger_uids.add(Ledger.narrow_to_uid(value))

    @override
    def discard(self, value: Ledger | Uid) -> None:
        self.ledger_uids.discard(Ledger.narrow_to_uid(value))
