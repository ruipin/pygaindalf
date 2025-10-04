# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from typing import TYPE_CHECKING

from pydantic import Field, InstanceOf

from ...collections import OrderedViewSet
from ..entity import EntitySchemaBase
from ..instrument import Instrument
from ..transaction import Transaction


class LedgerSchema[T_Transaction_Set: OrderedViewSet[Transaction]](EntitySchemaBase, metaclass=ABCMeta):
    # MARK: InstrumentRecord
    instrument: InstanceOf[Instrument] = Field(
        json_schema_extra={"readOnly": True},
        description="The financial instrument associated with this ledger, such as a stock, bond, or currency.",
    )

    # MARK: Transactions
    if TYPE_CHECKING:
        transactions: T_Transaction_Set = Field(default=...)
    else:
        transactions: OrderedViewSet[Transaction] = Field(
            default_factory=OrderedViewSet[Transaction],
            description="A set of transactions associated with this ledger.",
        )
