# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest

from app.portfolio.models.entity.entity_log import EntityLog, EntityModificationType
from app.portfolio.models.instrument import Instrument
from app.portfolio.models.instrument.instrument_type import InstrumentType
from app.util.helpers.currency import Currency


@pytest.mark.portfolio
@pytest.mark.instrument
class TestInstrumentEntity:
    def test_entity_wraps_record_and_reuses_instance(self):
        inst = Instrument(
            ticker="AAPL",
            type=InstrumentType.EQUITY,
            currency=Currency("USD"),
        )

        assert inst.uid == inst.record.uid
        assert inst.ticker == "AAPL"
        assert inst.currency == Currency("USD")

        by_uid = Instrument.by_uid(inst.uid)
        assert inst is by_uid

    def test_entity_initialization_sets_identifiers_and_audit(self):
        inst = Instrument(
            ticker="AAPL",
            type=InstrumentType.EQUITY,
            currency=Currency("USD"),
        )

        record = inst.record

        assert inst.instance_name == "AAPL"
        assert inst.uid.namespace == "Instrument"
        assert inst.uid.id == "AAPL"
        assert record.version == 1

        assert record.entity_log.entity_uid == inst.uid
        assert len(record.entity_log) == 1
        assert record.entity_log.exists is True
        assert record.entity_log.next_version == 2

    def test_entity_instance_lookup_preserves_singleton(self):
        inst = Instrument(
            isin="US0378331005",
            ticker="AAPL",
            type=InstrumentType.EQUITY,
            currency=Currency("USD"),
        )

        by_ticker = Instrument.instance(ticker="AAPL")
        by_isin = Instrument.instance(isin="US0378331005")

        assert by_ticker is inst
        assert by_isin is inst

        # Re-instantiating with conflicting data should raise an error
        inst_again = None
        with pytest.raises(ValueError, match=r"Expected 'currency' value 'Currency\.USD' but got 'Currency\.EUR'\."):
            inst_again = Instrument(ticker="AAPL", type=InstrumentType.EQUITY, currency=Currency("EUR"))

        assert inst_again is None
        assert inst.currency == Currency("USD")

    def test_entity_updates_and_audit_log(self):
        inst = Instrument(
            ticker="AAPL",
            type=InstrumentType.EQUITY,
            currency=Currency("USD"),
        )

        log = inst.record.entity_log
        assert log.version == 1

        inst.update(currency=Currency("GBP"))
        assert inst.currency == Currency("GBP")
        assert inst.record.version == 2

        inst.update(currency=Currency("EUR"))
        assert inst.currency == Currency("EUR")
        assert inst.record.version == 3

        entry_v1 = log.get_entry_by_version(1)
        assert entry_v1 is not None and entry_v1.what == EntityModificationType.CREATED
        if EntityLog.TRACK_ENTITY_DIFF:
            assert entry_v1.diff == {"ticker": "AAPL", "type": InstrumentType.EQUITY, "currency": Currency("USD")}

        entry_v2 = log.get_entry_by_version(2)
        assert entry_v2 is not None and entry_v2.what == EntityModificationType.UPDATED
        if EntityLog.TRACK_ENTITY_DIFF:
            assert entry_v2.diff == {"currency": Currency("GBP")}

        entry_v3 = log.get_entry_by_version(3)
        assert entry_v3 is not None and entry_v3.what == EntityModificationType.UPDATED
        if EntityLog.TRACK_ENTITY_DIFF:
            assert entry_v3.diff == {"currency": Currency("EUR")}

        # Simulate deletion via the entity log utilities
        log.on_delete_record(inst.record)  # TODO: Should be done via inst.delete() once fixed
        assert log.exists is False
        assert log.version == 4
        entry_v4 = log.get_entry_by_version(4)
        assert entry_v4 is not None and entry_v4.what == EntityModificationType.DELETED
        if EntityLog.TRACK_ENTITY_DIFF:
            assert entry_v4.diff == {"ticker": None, "type": None, "currency": None}

    def test_entity_tracks_superseding_record(self):
        inst = Instrument(
            ticker="AAPL",
            type=InstrumentType.EQUITY,
            currency=Currency("USD"),
        )
        record = inst.record

        Instrument(
            ticker="MSFT",
            type=InstrumentType.EQUITY,
            currency=Currency("USD"),
        )

        inst2 = inst.update(
            ticker="AAPL",
            currency=Currency("EUR"),
        )
        record2 = inst2.record

        assert inst is inst2
        assert record2 is not record
        assert record.superseded
        assert record2 is record.superseding
        assert inst2.currency == Currency("EUR")
