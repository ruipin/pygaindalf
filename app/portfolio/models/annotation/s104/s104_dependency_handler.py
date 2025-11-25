# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Any, override

from ....collections.journalled.set.ordered_view_set import JournalledOrderedViewSet
from ...entity import EntityDependencyEventHandlerImpl, EntityDependencyEventType
from ...ledger import LedgerRecord
from ...transaction import TransactionRecord
from ..transaction_annotation import TransactionAnnotationRecord


# MARK: Dependency handler
class S104AnnotationDependencyHandler(
    EntityDependencyEventHandlerImpl[TransactionAnnotationRecord, TransactionRecord | LedgerRecord],
    init=False,
):
    on_updated = True
    on_deleted = True

    @staticmethod
    @override
    def entity_matchers(owner: TransactionAnnotationRecord, record: TransactionRecord | LedgerRecord) -> bool:
        return record is owner.record_parent or record is owner.transaction.record_parent or record.instance_parent is owner

    @staticmethod
    @override
    def attribute_matchers(owner: TransactionAnnotationRecord, record: TransactionRecord | LedgerRecord, attribute: str, value: Any) -> bool:
        if isinstance(record, LedgerRecord):
            if attribute != "transactions":
                return False

            assert isinstance(value, JournalledOrderedViewSet), "Expected value to be JournalledOrderedViewSet"
            frontier_sort_key = value.frontier_sort_key
            if frontier_sort_key is None:
                return False

            self_sort_key = owner.transaction.sort_key()
            return bool(frontier_sort_key <= self_sort_key)
        else:
            return attribute in ("type", "date", "quantity")

    @staticmethod
    @override
    def handler(
        owner: TransactionAnnotationRecord,
        event: EntityDependencyEventType,
        record: TransactionRecord | LedgerRecord,
        *,
        matched_attributes: frozenset[str] | None = None,
    ) -> None:
        msg = f"S104 annotation detected unsupported dependency event {event} for record {record}"
        raise NotImplementedError(msg)
