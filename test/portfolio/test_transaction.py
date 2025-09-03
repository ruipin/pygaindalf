# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime
from decimal import Decimal

import pytest
from iso4217 import Currency

from app.portfolio.models.instrument import Instrument
from app.portfolio.models.transaction import Transaction, TransactionType
from app.portfolio.models.entity.entity_audit_log import EntityAuditType, EntityAuditLog


@pytest.mark.portfolio
@pytest.mark.transaction
class TestTransaction:
    def test_basic_initialization_sets_uid_namespace_and_audit(self):
        inst = Instrument(
            ticker="AAPL",
            currency=Currency("USD"),
        )

        tx = Transaction(
            instrument_uid=inst.uid,
            type=TransactionType.BUY,
            date=datetime.date(2025, 1, 1),
            quantity=Decimal("10"),
            consideration=Decimal("1500"),
            fees=Decimal("5"),
        )

        # UID namespace encodes instrument name
        assert tx.uid.namespace == f"Transaction-{inst.instance_name}"
        assert tx.uid.id == 1  # first transaction for this instrument namespace
        assert tx.instance_name == str(tx.uid)

        # Instrument linkage via computed property
        assert tx.instrument is inst
        assert tx.instrument_uid == inst.uid

        # Audit basics
        assert tx.version == 1
        assert tx.entity_log.entity_uid == tx.uid
        assert len(tx.entity_log) == 1
        assert tx.entity_log.exists is True
        assert tx.entity_log.next_version == 2

    def test_multiple_transactions_increment_uid_id_and_audit(self):
        inst = Instrument(
            ticker="MSFT",
            currency=Currency("USD"),
        )

        tx1 = Transaction(
            instrument_uid=inst.uid,
            type=TransactionType.BUY,
            date=datetime.date(2025, 1, 2),
            quantity=Decimal("5"),
            consideration=Decimal("750"),
        )
        tx2 = Transaction(
            instrument_uid=inst.uid,
            type=TransactionType.SELL,
            date=datetime.date(2025, 1, 3),
            quantity=Decimal("2"),
            consideration=Decimal("320"),
        )

        assert tx1.uid.namespace == tx2.uid.namespace == f"Transaction-MSFT"
        assert tx1.uid.id == 1
        assert tx2.uid.id == 2

        # Each has independent audit log (same uid namespace but different IDs)
        assert tx1.entity_log.entity_uid == tx1.uid
        assert tx2.entity_log.entity_uid == tx2.uid

    def test_update_creates_new_version_and_audit_entry(self):
        inst = Instrument(
            ticker="GOOGL",
            currency=Currency("USD"),
        )
        tx1 = Transaction(
            instrument_uid=inst.uid,
            type=TransactionType.BUY,
            date=datetime.date(2025, 2, 1),
            quantity=Decimal("3"),
            consideration=Decimal("405"),
        )

        # Update via entity update mechanism (increase quantity)
        tx2 = tx1.update(quantity=Decimal("4"))

        assert tx2 is not tx1
        assert tx1.version == 1
        assert tx2.version == 2
        assert tx1.entity_log is tx2.entity_log
        assert tx1.superseded
        assert not tx2.superseded
        assert len(tx2.entity_log) == 2

        entry_v1 = tx2.entity_log.get_entry_by_version(1)
        assert entry_v1 is not None
        assert entry_v1.what == EntityAuditType.CREATED
        if EntityAuditLog.TRACK_ENTITY_DIFF:
            assert entry_v1.diff == {
                'instrument_uid': inst.uid,
                'type': TransactionType.BUY,
                'date': datetime.date(2025, 2, 1),
                'quantity': Decimal("3"),
                'consideration': Decimal("405"),
                'fees': Decimal("0"),
            }

        entry_v2 = tx2.entity_log.get_entry_by_version(2)
        assert entry_v2 is not None
        assert entry_v2.what == EntityAuditType.UPDATED
        if EntityAuditLog.TRACK_ENTITY_DIFF:
            assert entry_v2.diff == {
                'quantity': Decimal("4"),
            }

    def test_validation_rejects_wrong_instrument_uid_namespace(self):
        # Forge a UID with wrong namespace
        from app.portfolio.models.uid import Uid
        bad_uid = Uid(namespace="Wrong", id="ORCL")

        with pytest.raises((ValueError, TypeError)):
            Transaction(
                instrument_uid=bad_uid,
                type=TransactionType.BUY,
                date=datetime.date(2025, 3, 1),
                quantity=Decimal("1"),
                consideration=Decimal("100"),
            )
