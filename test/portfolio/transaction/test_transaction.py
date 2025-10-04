# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime

from decimal import Decimal

import pytest

from app.portfolio.models.entity.entity_log import EntityLog, EntityModificationType
from app.portfolio.models.transaction import Transaction, TransactionType


@pytest.mark.portfolio
@pytest.mark.transaction
class TestTransactionEntity:
    def test_entity_initialization_sets_uid_namespace_and_audit(self):
        tx = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 1, 1),
            quantity=Decimal(10),
            consideration=Decimal(1500),
            fees=Decimal(5),
        )

        assert tx.uid.namespace == "Transaction"
        assert tx.uid.id == 1
        assert tx.instance_name == str(tx.uid)

        record = tx.record
        assert record.version == 1
        assert record.entity_log.entity_uid == tx.uid
        assert len(record.entity_log) == 1
        assert record.entity_log.exists is True
        assert record.entity_log.next_version == 2

    def test_entity_wraps_record_and_reuses_instance(self):
        tx = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 1, 1),
            quantity=Decimal(5),
            consideration=Decimal(500),
            fees=Decimal(5),
        )

        assert tx.uid.namespace == "Transaction"
        assert tx.quantity == Decimal(5)
        assert tx.consideration == Decimal(500)
        assert tx.fees == Decimal(5)
        assert Transaction.by_uid(tx.uid) is tx

    def test_multiple_transactions_increment_uid_and_audit(self):
        tx1 = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 1, 2),
            quantity=Decimal(5),
            consideration=Decimal(750),
        )
        tx2 = Transaction(
            type=TransactionType.SELL,
            date=datetime.date(2025, 1, 3),
            quantity=Decimal(2),
            consideration=Decimal(320),
        )

        assert tx1.uid.namespace == tx2.uid.namespace == "Transaction"
        assert tx1.uid.id == 1
        assert tx2.uid.id == 2

        assert tx1.record.entity_log.entity_uid == tx1.uid
        assert tx2.record.entity_log.entity_uid == tx2.uid

    def test_entity_tracks_record_updates(self):
        tx = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 2, 1),
            quantity=Decimal(2),
            consideration=Decimal(220),
        )

        original_record = tx.record
        tx.update(quantity=Decimal(3))
        updated_record = tx.record

        assert updated_record is not original_record
        assert original_record.superseded
        assert updated_record is original_record.superseding
        assert tx.quantity == Decimal(3)
        assert Transaction.by_uid(tx.uid) is tx

        log = tx.record.entity_log
        assert log.version == 2
        entry_v1 = log.get_entry_by_version(1)
        assert entry_v1 is not None and entry_v1.what == EntityModificationType.CREATED
        if EntityLog.TRACK_ENTITY_DIFF:
            assert entry_v1.diff == {
                "type": TransactionType.BUY,
                "date": datetime.date(2025, 2, 1),
                "quantity": Decimal(2),
                "consideration": Decimal(220),
                "fees": Decimal(0),
            }

        entry_v2 = log.get_entry_by_version(2)
        assert entry_v2 is not None and entry_v2.what == EntityModificationType.UPDATED
        if EntityLog.TRACK_ENTITY_DIFF:
            assert entry_v2.diff == {"quantity": Decimal(3)}
