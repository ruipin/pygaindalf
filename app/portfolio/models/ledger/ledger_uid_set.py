# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime

from typing import override, Iterable, Any, TYPE_CHECKING, Self
from collections.abc import Set, MutableSet

from ...collections.ordered_view import OrderedViewSet, OrderedViewFrozenSet
from ...collections.journalled import JournalledOrderedViewSet
from ..uid import Uid
from .ledger import Ledger


class OrderedViewFrozenLedgerUidSet(OrderedViewFrozenSet[Uid]):
    @classmethod
    @override
    def get_mutable_type(cls, source : type[OrderedViewFrozenSet] | None = None) -> type[MutableSet[Uid]]:
        return OrderedViewLedgerUidSet

    @classmethod
    @override
    def get_journalled_type(cls) -> type[JournalledOrderedViewSet]:
        return JournalledOrderedViewLedgerUidSet

    @classmethod
    @override
    def _validate_item(cls, concrete_item_type : type[Uid], item: Any) -> None:
        super()._validate_item(concrete_item_type, item)

        transaction_ns = Ledger.uid_namespace()
        if not isinstance(item, Uid):
            raise TypeError(f"Expected 'value' elements to be Uid instances, got {type(item).__name__}.")
        if item.namespace != transaction_ns:
            raise ValueError(f"Invalid transaction UID namespace: expected '{transaction_ns}', got '{item.namespace}'.")



class OrderedViewLedgerUidSet(OrderedViewFrozenLedgerUidSet, OrderedViewSet[Uid]):
    @classmethod
    @override
    def get_immutable_type(cls, source : type[OrderedViewSet] | None = None) -> type[Set[Uid]]:
        return OrderedViewFrozenLedgerUidSet



class JournalledOrderedViewLedgerUidSet(JournalledOrderedViewSet[Uid, OrderedViewLedgerUidSet, OrderedViewFrozenLedgerUidSet]):
    pass
