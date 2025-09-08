# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest

from iso4217 import Currency

from app.portfolio.models.instrument.instrument import Instrument
from app.portfolio.models.entity.entity_audit_log import EntityAuditType, EntityAuditLog



@pytest.mark.portfolio
@pytest.mark.instrument
class TestInstrument:
    def test_initialization_sets_identifiers_uid_and_audit(self):
        i = Instrument(
            ticker='AAPL',
            currency=Currency('USD'),
        )

        # Instance naming and UID
        assert i.instance_name == "AAPL"
        assert i.uid.namespace == "Instrument"
        assert i.uid.id == "AAPL"
        assert i.version == 1

        # Audit log basics
        assert i.entity_log.entity_uid == i.uid
        assert len(i.entity_log) == 1
        assert i.entity_log.exists is True
        assert i.entity_log.next_version == 2

    def test_singleton_lookup_via_classmethod_instance(self):
        i1 = Instrument(
            isin="US0378331005",
            ticker="AAPL",
            currency=Currency("USD"),
        )

        # Lookup by ticker
        i2 = Instrument.instance(ticker="AAPL")
        assert i2 is i1

        # Lookup by ISIN
        i3 = Instrument.instance(isin="US0378331005")
        assert i3 is i1

    def test_reinitialization(self):
        i = Instrument.model_validate({
            "ticker": "AAPL",
            "currency": Currency("USD"),
        })

        # Re-initializing same identifier with different attributes should error
        with pytest.raises(Exception):
            Instrument.model_validate({
                "ticker": "AAPL",
                "currency": Currency("EUR"),
            })

        # Re-initializing with same attributes should not error
        i2 = Instrument.model_validate({
            "ticker": "AAPL",
            "currency": Currency("USD"),
        })

        assert i is i2

    def test_updates_and_audit_log(self):
        i1 = Instrument(
            ticker='AAPL',
            currency=Currency('USD'),
        )

        assert i1.currency == Currency('USD')
        assert i1.version == 1

        # Update the instrument
        i2 = Instrument(
            ticker='AAPL',
            currency=Currency('GBP'),
            version=i1.entity_log.next_version,  # Increment version
        )

        assert i2 is not i1
        assert i1.version == 1
        assert i2.version == 2
        assert i1.entity_log is i2.entity_log
        assert i1.superseded
        assert not i2.superseded
        assert i2.entity_log.exists is True
        assert len(i2.entity_log) == 2
        assert i2.entity_log.next_version == 3
        assert i2.currency == Currency('GBP')

        # Update the instrument using the 'update' method
        i3 = i2.update(
            currency=Currency('EUR'),
        )

        assert i3 is not i1
        assert i3 is not i2
        assert i1.version == 1
        assert i2.version == 2
        assert i3.version == 3
        assert i1.entity_log is i3.entity_log
        assert i2.entity_log is i3.entity_log
        assert i1.superseded
        assert i2.superseded
        assert not i3.superseded
        assert i3.entity_log.exists is True
        assert len(i3.entity_log) == 3
        assert i3.entity_log.next_version == 4
        assert i3.currency == Currency('EUR')

        # Check the audit log entries
        entry_v1 = i2.entity_log.get_entry_by_version(1)
        assert entry_v1 is not None
        assert entry_v1.what == EntityAuditType.CREATED
        assert entry_v1.version == 1
        if EntityAuditLog.TRACK_ENTITY_DIFF:
            assert entry_v1.diff == {
                'ticker'  : 'AAPL',
                'currency': Currency('USD'),
            }

        entry_v2 = i2.entity_log.get_entry_by_version(2)
        assert entry_v2 is not None
        assert entry_v2.what == EntityAuditType.UPDATED
        assert entry_v2.version == 2
        if EntityAuditLog.TRACK_ENTITY_DIFF:
            assert entry_v2.diff == {
                'currency': Currency('GBP'),
            }

        entry_v3 = i2.entity_log.get_entry_by_version(3)
        assert entry_v3 is not None
        assert entry_v3.what == EntityAuditType.UPDATED
        assert entry_v3.version == 3
        if EntityAuditLog.TRACK_ENTITY_DIFF:
            assert entry_v3.diff == {
                'currency': Currency('EUR'),
            }

        # 'Delete' the instrument
        entity_log = i3.entity_log
        entity_log.on_delete(i3)

        assert entity_log.exists is False
        assert entity_log.version == 4
        entry_v4 = entity_log.get_entry_by_version(4)
        assert entry_v4 is not None
        assert entry_v4.what == EntityAuditType.DELETED
        assert entry_v4.version == 4
        if EntityAuditLog.TRACK_ENTITY_DIFF:
            assert entry_v4.diff == {
                'ticker'  : None,
                'currency': None,
            }