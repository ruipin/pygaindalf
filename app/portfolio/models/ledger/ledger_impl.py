# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime

from abc import ABCMeta
from collections.abc import Iterator
from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, override

from ....util.helpers.empty_class import empty_class
from ....util.models.uid import Uid
from ...collections import OrderedViewSet
from ..entity import EntityImpl
from ..transaction import Transaction, TransactionRecord
from .ledger_schema import LedgerSchema


if TYPE_CHECKING:
    from decimal import Decimal

    from ....util.helpers.decimal_currency import DecimalCurrency
    from ..annotation.s104 import S104HoldingsAnnotation


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

    @property
    def first(self) -> Transaction | None:
        return self.transactions[0] if self.transactions else None

    @property
    def last(self) -> Transaction | None:
        return self.transactions[-1] if self.transactions else None

    @override
    def __repr__(self) -> str:
        return super().__repr__().replace(">", f", transactions={self.transactions!r}>")

    # MARK: S104
    def get_s104_holdings_or_none(self, *, at: datetime.date | Transaction | None = None) -> S104HoldingsAnnotation | None:
        if at is None:
            at = self.last

        if isinstance(at, datetime.date):
            for txn in reversed(self.transactions):
                if txn.date <= at:
                    at = txn
                    break
            else:
                return None

        if not isinstance(at, Transaction):
            msg = f"Parameter 'at' must be a date or Transaction, got {type(at).__name__}"
            raise TypeError(msg)

        return at.get_s104_holdings_or_none()

    def get_s104_holdings(self, *, at: datetime.date | Transaction | None = None) -> S104HoldingsAnnotation:
        if (ann := self.get_s104_holdings_or_none(at=at)) is None:
            msg = "S104 holdings annotation requested but not found. Please ensure you have run a S104 annotator."
            raise ValueError(msg)
        return ann

    @property
    def s104_cost_basis(self) -> DecimalCurrency:
        ann = self.get_s104_holdings()
        return ann.cost_basis

    @property
    def s104_shares(self) -> Decimal:
        ann = self.get_s104_holdings()
        return ann.quantity
