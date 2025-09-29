# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING

from pydantic import Field

from ...collections import OrderedViewUidSet
from ...util.uid import Uid
from ..entity import EntityFieldsBase
from ..ledger import Ledger


class PortfolioFields[T_Uid_Set: AbstractSet[Uid]](EntityFieldsBase, metaclass=ABCMeta):
    # MARK: Ledgers
    if TYPE_CHECKING:
        ledger_uids: T_Uid_Set = Field(default=...)
    else:
        ledger_uids: OrderedViewUidSet[Ledger] = Field(
            default_factory=OrderedViewUidSet[Ledger],
            description="A set of ledger Uids associated with this portfolio.",
        )
