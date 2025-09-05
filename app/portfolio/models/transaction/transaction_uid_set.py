# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime

from typing import override, Iterable, Any, TYPE_CHECKING
from collections.abc import Set, MutableSet

from ...collections.ordered_view import OrderedViewSet, OrderedViewFrozenSet
from ...collections.journalled import JournalledOrderedViewSet
from ..uid import Uid
from .transaction import Transaction

if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison


class OrderedViewFrozenTransactionUidSet(OrderedViewFrozenSet[Uid]):
    @classmethod
    @override
    def get_mutable_type(cls) -> type[MutableSet[Uid]]:
        return OrderedViewTransactionUidSet

    @classmethod
    @override
    def get_journalled_type(cls) -> type[JournalledOrderedViewSet]:
        return JournalledOrderedViewTransactionUidSet

    @override
    def _sort_key(self, item : Uid) -> 'SupportsRichComparison':
        txn = Transaction.by_uid(item)
        if txn is None:
            raise ValueError(f"No transaction found for UID {item}.")
        return (txn.date, txn.uid)

    @classmethod
    @override
    def _validate_item(cls, concrete_item_type : type[Uid], item: Any) -> None:
        super()._validate_item(concrete_item_type, item)

        transaction_ns = Transaction.uid_namespace()
        if not isinstance(item, Uid):
            raise TypeError(f"Expected 'value' elements to be Uid instances, got {type(item).__name__}.")
        if not item.namespace.startswith(transaction_ns):
            raise ValueError(f"Invalid transaction UID namespace: expected it to start with '{transaction_ns}', got '{item.namespace}'.")



class OrderedViewTransactionUidSet(OrderedViewFrozenTransactionUidSet, OrderedViewSet[Uid]):
    @classmethod
    @override
    def get_immutable_type(cls) -> type[Set[Uid]]:
        return OrderedViewFrozenTransactionUidSet



class JournalledOrderedViewTransactionUidSet(JournalledOrderedViewSet[Uid, OrderedViewTransactionUidSet, OrderedViewFrozenTransactionUidSet]):
    pass
