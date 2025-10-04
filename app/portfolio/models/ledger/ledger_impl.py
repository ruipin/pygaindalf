# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import Iterator
from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, override

from ....util.helpers.empty_class import empty_class
from ...collections import OrderedViewSet
from ...util.uid import Uid
from ..entity import EntityImpl
from ..transaction import Transaction, TransactionRecord
from .ledger_schema import LedgerSchema


class LedgerImpl[
    T_Transaction_Set: OrderedViewSet[Transaction],
](
    EntityImpl,
    LedgerSchema[T_Transaction_Set] if TYPE_CHECKING else empty_class(),
    AbstractSet[Transaction],
    metaclass=ABCMeta,
):
    # MARK: Transactions
    def __getitem__(self, index: int | Uid) -> Transaction:
        if isinstance(index, int):
            return self.transactions[index]

        elif isinstance(index, Uid):
            if index not in self.transactions:
                msg = f"Transaction with UID {index} not found in ledger"
                raise KeyError(msg)
            return Transaction.by_uid(index)

        else:
            msg = f"Index must be an int or Uid, got {type(index).__name__}"
            raise KeyError(msg)

    # MARK: Set ABC
    @override
    def __contains__(self, value: object) -> bool:
        if not isinstance(value, (Transaction, TransactionRecord, Uid)):
            return False
        return Transaction.narrow_to_uid(value) in self.transactions

    @override
    def __iter__(self) -> Iterator[Transaction]:  # pyright: ignore[reportIncompatibleMethodOverride] since we are overriding the pydantic.BaseModel iterator on purpose
        return iter(self.transactions)

    @override
    def __len__(self) -> int:
        return len(self.transactions)

    @property
    def length(self) -> int:
        return len(self.transactions)

    @override
    def __repr__(self) -> str:
        return super().__repr__().replace(">", f", transactions={self.transactions!r}>")
