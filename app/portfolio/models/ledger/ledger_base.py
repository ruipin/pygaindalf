# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from functools import cached_property

from collections.abc import Set, Sequence
from abc import abstractmethod, ABCMeta
from typing import override, Iterator, TYPE_CHECKING

from ..transaction import Transaction
from ..uid import Uid
from ..transaction import OrderedViewFrozenTransactionUidSet, UidProxyOrderedViewTransactionFrozenSet


class LedgerBase[T_Uid_Set : OrderedViewFrozenTransactionUidSet, T_Proxy_Set : UidProxyOrderedViewTransactionFrozenSet](Set[Transaction], metaclass=ABCMeta):
    if TYPE_CHECKING:
        transaction_uids : T_Uid_Set

    @cached_property
    @abstractmethod
    def transactions(self) -> T_Proxy_Set:
        raise NotImplementedError("Subclasses must implement transactions property")


    # MARK: Custom __getitem__
    def __getitem__(self, index : int | Uid) -> Transaction:
        if isinstance(index, int):
            return self.transactions[index]

        elif isinstance(index, Uid):
            if index not in self.transaction_uids:
                raise KeyError(f"Transaction with UID {index} not found in ledger")
            if (transaction := Transaction.by_uid(index)) is None:
                raise KeyError(f"Transaction with UID {index} not found")
            return transaction

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