# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, Any, override

from pydantic import field_validator

from ....util.helpers.empty_class import EmptyClass
from ...util.uid import Uid
from ..entity import Entity
from ..entity.instance_store import NamedInstanceStoreEntityMixin
from ..instrument.instrument import Instrument
from .ledger_base import LedgerBase
from .ledger_fields import LedgerFields
from .ledger_journal import LedgerJournal


if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison

    from .ledger_proxy import LedgerProxy  # noqa: F401


class Ledger(
    LedgerBase,
    LedgerFields if not TYPE_CHECKING else EmptyClass,
    NamedInstanceStoreEntityMixin,
    Entity[LedgerJournal, "LedgerProxy"],
):
    # MARK: Instrument
    @field_validator("instrument_uid", mode="before")
    @classmethod
    def _validate_instrument_uid(cls, value: Any) -> Uid:
        if not isinstance(value, Uid):
            msg = f"Expected 'instrument_uid' to be a Uid, got {type(value).__name__}."
            raise TypeError(msg)
        if value.namespace != (instrument_ns := Instrument.uid_namespace()):
            msg = f"Invalid instrument UID namespace: expected '{instrument_ns}', got '{value.namespace}'."
            raise ValueError(msg)
        return value

    @classmethod
    def by_instrument(cls, instrument: Instrument) -> Ledger | None:
        """Return the ledger instance associated with the given instrument.

        If no ledger exists for the instrument, returns None.
        """
        if not isinstance(instrument, Instrument):
            msg = f"Expected 'instrument' to be an Instrument instance, got {type(instrument).__name__}."
            raise TypeError(msg)

        result = cls.instance(instance_name=cls.calculate_instance_name_from_dict({"instrument_uid": instrument.uid}))
        if not isinstance(result, cls):
            msg = f"Expected 'result' to be an instance of {cls.__name__}, got {type(result).__name__}."
            raise TypeError(msg)
        return result

    # MARK: Instance Name
    @property
    @override
    def instance_name(self) -> str:
        return self.calculate_instance_name_from_dict(self.__dict__, allow_missing_instrument=True)

    @classmethod
    @override
    def calculate_instance_name_from_dict(cls, data: dict[str, Any], allow_missing_instrument: bool = False) -> str:
        """Convert the provided keyword arguments to an instance name.

        This method should be implemented by subclasses to define how to derive the instance name.
        """
        instrument_uid = data.get("instrument_uid")
        if instrument_uid is None:
            msg = f"{cls.__name__}.calculate_instance_name_from_dict requires 'instrument_uid' in data to generate an instance name."
            raise TypeError(msg)
        instrument = Instrument.by_uid_or_none(instrument_uid)
        if instrument is None:
            if not allow_missing_instrument:
                msg = f"{cls.__name__}.calculate_instance_name_from_dict requires 'instrument_uid' to correspond to a valid Instrument to generate an instance name."
                raise TypeError(msg)
            instrument_name = "None"
        else:
            instrument_name = instrument.instance_name
            if instrument_name is None:
                msg = f"Instrument with UID '{instrument_uid}' does not have a valid instance name."
                raise ValueError(msg)

        return f"{cls.__name__}@{instrument_name}"

    # MARK: Utilities
    @override
    def sort_key(self) -> SupportsRichComparison:
        return (self.instance_name, self.uid)
