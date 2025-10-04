# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING

from pydantic import Field

from ...collections import OrderedViewSet
from ..entity import EntitySchemaBase
from ..ledger import Ledger


class PortfolioSchema[T_Ledger_Set: AbstractSet[Ledger]](EntitySchemaBase, metaclass=ABCMeta):
    # MARK: Ledgers
    if TYPE_CHECKING:
        ledgers: T_Ledger_Set = Field(default=...)
    else:
        ledgers: OrderedViewSet[Ledger] = Field(
            default_factory=OrderedViewSet[Ledger],
            description="A set of ledgers associated with this portfolio.",
        )
