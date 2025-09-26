# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Set
from abc import ABCMeta
from typing import TYPE_CHECKING
from pydantic import Field

from ..uid import Uid
from ..transaction import OrderedViewFrozenTransactionUidSet
from ..entity import EntityFieldsBase


class LedgerFields[T_Uid_Set : Set[Uid]](EntityFieldsBase, metaclass=ABCMeta):
    # MARK: Instrument
    instrument_uid : Uid = Field(
        json_schema_extra={'readOnly': True},
        description="The financial instrument associated with this ledger, such as a stock, bond, or currency."
    )


    # MARK: Transactions
    if TYPE_CHECKING:
        transaction_uids : T_Uid_Set = Field(default=...)
    else:
        transaction_uids : OrderedViewFrozenTransactionUidSet = Field(
            default_factory=OrderedViewFrozenTransactionUidSet,
            description="A set of transaction Uids associated with this ledger."
        )