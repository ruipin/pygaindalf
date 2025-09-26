# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from functools import cached_property

from collections.abc import Set
from abc import abstractmethod, ABCMeta
from typing import override, Iterator, TYPE_CHECKING
from pydantic import Field

from ....util.helpers.empty_class import EmptyClass
from ....util.helpers import generics

from ..instrument import Instrument
from ..transaction import Transaction
from ..uid import Uid
from ..transaction import OrderedViewFrozenTransactionUidSet, UidProxyOrderedViewTransactionFrozenSet
from ..entity import EntityBase

from .ledger_fields import LedgerFields


class LedgerBase[
    T_Uid_Set : Set[Uid],
    T_Proxy_Set : UidProxyOrderedViewTransactionFrozenSet
](
    EntityBase,
    LedgerFields[T_Uid_Set] if TYPE_CHECKING else EmptyClass,
    Set[Transaction],
    metaclass=ABCMeta
):
    # MARK: Instrument
    @property
    def instrument(self) -> Instrument:
        return Instrument.by_uid(self.instrument_uid)


    # MARK: Transactions
    get_proxy_set_type = generics.GenericIntrospectionMethod[T_Proxy_Set]()

    @cached_property
    def transactions(self) -> T_Proxy_Set:
        return self.get_proxy_set_type(origin=True)(owner=self, field='transaction_uids')

    def __getitem__(self, index : int | Uid) -> Transaction:
        if isinstance(index, int):
            return self.transactions[index]

        elif isinstance(index, Uid):
            if index not in self.transaction_uids:
                raise KeyError(f"Transaction with UID {index} not found in ledger")
            return Transaction.by_uid(index)

        else:
            raise KeyError(f"Index must be an int or Uid, got {type(index).__name__}")


    # MARK: Set ABC
    @override
    def __contains__(self, value : object) -> bool:
        if not isinstance(value, (Transaction, Uid)):
            return False
        return Transaction.narrow_to_uid(value) in self.transaction_uids

    @override
    def __iter__(self) -> Iterator[Transaction]: # pyright: ignore[reportIncompatibleMethodOverride] since we are overriding the pydantic.BaseModel iterator on purpose
        return iter(self.transactions)

    @override
    def __len__(self):
        return len(self.transaction_uids)

    @property
    def length(self) -> int:
        return len(self.transaction_uids)

    @override
    def __repr__(self) -> str:
        return super().__repr__().replace('>', f", transactions={repr(self.transaction_uids)}>")