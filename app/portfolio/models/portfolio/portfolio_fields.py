# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Set
from abc import ABCMeta
from typing import TYPE_CHECKING
from pydantic import Field

from ..uid import Uid
from ..ledger import OrderedViewFrozenLedgerUidSet
from ..entity import EntityFieldsBase


class PortfolioFields[T_Uid_Set : Set[Uid]](EntityFieldsBase, metaclass=ABCMeta):
    # MARK: Ledgers
    if TYPE_CHECKING:
        ledger_uids : T_Uid_Set = Field(default=...)
    else:
        ledger_uids : OrderedViewFrozenLedgerUidSet = Field(
            default_factory=OrderedViewFrozenLedgerUidSet,
            description="A set of ledger Uids associated with this portfolio."
        )