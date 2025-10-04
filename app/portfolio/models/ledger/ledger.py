# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, override

from ....util.helpers.empty_class import empty_class
from ..entity import Entity, NamedInstanceStoreMixin
from ..instrument import Instrument, InstrumentRecord
from .ledger_impl import LedgerImpl
from .ledger_journal import LedgerJournal
from .ledger_record import LedgerRecord


if TYPE_CHECKING:
    from ...util.uid import Uid


class Ledger(
    LedgerImpl if TYPE_CHECKING else empty_class(),
    NamedInstanceStoreMixin,
    Entity[LedgerRecord, LedgerJournal],
    init=False,
    unsafe_hash=True,
):
    # MARK: Instrument
    @classmethod
    def by_instrument(cls, instrument: Instrument | InstrumentRecord | Uid) -> Self | None:
        """Return the ledger instance associated with the given instrument.

        If no ledger exists for the instrument, returns None.
        """
        instrument = Instrument.narrow_to_instance(instrument)
        result = cls.instance(instance_name=cls.calculate_instance_name_from_dict({"instrument": instrument}))
        if not isinstance(result, cls):
            msg = f"Expected 'result' to be an instance of {cls.__name__}, got {type(result).__name__}."
            raise TypeError(msg)
        return result

    # MARK: Instance Name
    @classmethod
    @override
    def calculate_instance_name_from_dict(cls, data: Mapping[str, Any], allow_missing_instrument: bool = False) -> str:
        """Convert the provided keyword arguments to an instance name.

        This method should be implemented by subclasses to define how to derive the instance name.
        """
        instrument = data.get("instrument")
        if instrument is None or not isinstance(instrument, Instrument):
            if not allow_missing_instrument:
                msg = (
                    f"{cls.__name__}.calculate_instance_name_from_dict requires 'instrument' to correspond to a valid Instrument to generate an instance name."
                )
                raise TypeError(msg)
            instrument_name = "None"
        else:
            instrument_name = instrument.instance_name
            if instrument_name is None:
                msg = f"Instrument '{instrument}' does not have a valid instance name."
                raise ValueError(msg)

        return f"{cls.__name__}@{instrument_name}"


LedgerRecord.register_entity_class(Ledger)
