# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override, TYPE_CHECKING, Iterator, Iterable
from pydantic import Field
from functools import cached_property
from collections.abc import MutableSet, Set

from ..entity import Entity, IncrementingUidEntity
from ..instrument.instrument import Instrument
from ..uid import Uid
from ..ledger import UidProxyOrderedViewLedgerFrozenSet, OrderedViewFrozenLedgerUidSet

from .portfolio_base import PortfolioBase
from .portfolio_journal import PortfolioJournal


class Portfolio(PortfolioBase, IncrementingUidEntity[PortfolioJournal]):
    @classmethod
    @override
    def get_journal_class(cls) -> type[PortfolioJournal]:
        return PortfolioJournal



    # MARK: Ledgers
    if TYPE_CHECKING:
        ledger_uids : Set[Uid] = Field(default_factory=frozenset)
    else:
        ledger_uids : OrderedViewFrozenLedgerUidSet = Field(default_factory=OrderedViewFrozenLedgerUidSet, description="A set of ledger Uids associated with this portfolio.")

    @cached_property
    def ledgers(self) -> UidProxyOrderedViewLedgerFrozenSet:
        return UidProxyOrderedViewLedgerFrozenSet(owner=self, field='ledger_uids')