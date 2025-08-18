# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest

from iso4217 import Currency

from app.portfolio.models.instrument import Instrument
from app.portfolio.models.ledger import Ledger


@pytest.mark.portfolio
@pytest.mark.ledger
class TestLedger:
    def test_initialization_uses_instrument_name_and_audit(self):
        inst = Instrument.model_validate({
            "ticker": "MSFT",
            "currency": Currency("USD"),
        })
        ledg = Ledger.model_validate({
            "instrument": inst,
        })

        # Name and linkage
        assert ledg.instance_name == f'Ledger@{inst.instance_name}'
        assert ledg.instrument is inst

        # Instance store lookup
        by_name = Ledger.by_instrument(inst)
        assert by_name is ledg

        # Audit basics
        assert ledg.version == 1
        assert ledg.entity_log.entity_uid == ledg.uid
        assert len(ledg.entity_log) == 1
        assert ledg.entity_log.exists is True
        assert ledg.entity_log.next_version == 2