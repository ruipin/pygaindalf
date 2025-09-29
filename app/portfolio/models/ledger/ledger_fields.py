# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING

from pydantic import Field

from ...collections import OrderedViewUidSet
from ...util.uid import Uid
from ..entity import EntityFieldsBase
from ..transaction import Transaction


class LedgerFields[T_Uid_Set: AbstractSet[Uid]](EntityFieldsBase, metaclass=ABCMeta):
    # MARK: Instrument
    instrument_uid: Uid = Field(
        json_schema_extra={"readOnly": True},
        description="The financial instrument associated with this ledger, such as a stock, bond, or currency.",
    )

    # MARK: Transactions
    if TYPE_CHECKING:
        transaction_uids: T_Uid_Set = Field(default=...)
    else:
        transaction_uids: OrderedViewUidSet[Transaction] = Field(
            default_factory=OrderedViewUidSet[Transaction],
            description="A set of transaction Uids associated with this ledger.",
        )
