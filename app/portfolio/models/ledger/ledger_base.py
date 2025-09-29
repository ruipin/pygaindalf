# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import Iterator
from collections.abc import Set as AbstractSet
from functools import cached_property
from typing import TYPE_CHECKING, override

from ....util.helpers import generics
from ....util.helpers.empty_class import EmptyClass
from ...collections import UidProxyOrderedViewMutableSet
from ...util.uid import Uid
from ..entity import EntityBase
from ..instrument import Instrument
from ..transaction import Transaction
from .ledger_fields import LedgerFields


class LedgerBase[
    T_Uid_Set: AbstractSet[Uid],
    T_Proxy_Set: UidProxyOrderedViewMutableSet[Transaction],
](
    EntityBase,
    LedgerFields[T_Uid_Set] if TYPE_CHECKING else EmptyClass,
    AbstractSet[Transaction],
    metaclass=ABCMeta,
):
    # MARK: Instrument
    @property
    def instrument(self) -> Instrument:
        return Instrument.by_uid(self.instrument_uid)

    # MARK: Transactions
    get_proxy_set_type = generics.GenericIntrospectionMethod[T_Proxy_Set]()

    @cached_property
    def transactions(self) -> T_Proxy_Set:
        return self.get_proxy_set_type(origin=True)(instance=self, field="transaction_uids")

    def __getitem__(self, index: int | Uid) -> Transaction:
        if isinstance(index, int):
            return self.transactions[index]

        elif isinstance(index, Uid):
            if index not in self.transaction_uids:
                msg = f"Transaction with UID {index} not found in ledger"
                raise KeyError(msg)
            return Transaction.by_uid(index)

        else:
            msg = f"Index must be an int or Uid, got {type(index).__name__}"
            raise KeyError(msg)

    # MARK: Set ABC
    @override
    def __contains__(self, value: object) -> bool:
        if not isinstance(value, (Transaction, Uid)):
            return False
        return Transaction.narrow_to_uid(value) in self.transaction_uids

    @override
    def __iter__(self) -> Iterator[Transaction]:  # pyright: ignore[reportIncompatibleMethodOverride] since we are overriding the pydantic.BaseModel iterator on purpose
        return iter(self.transactions)

    @override
    def __len__(self) -> int:
        return len(self.transaction_uids)

    @property
    def length(self) -> int:
        return len(self.transaction_uids)

    @override
    def __repr__(self) -> str:
        return super().__repr__().replace(">", f", transactions={self.transaction_uids!r}>")
