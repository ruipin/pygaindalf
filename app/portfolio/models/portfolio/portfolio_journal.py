# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import MutableSet
from typing import TYPE_CHECKING, override

from ...collections import OrderedViewMutableSet
from ...journal.journal import Journal
from ..ledger import Ledger
from .portfolio_impl import PortfolioImpl


if TYPE_CHECKING:
    from ...util.uid import Uid


class PortfolioJournal(
    PortfolioImpl[OrderedViewMutableSet[Ledger]],
    Journal,
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
