# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime
import weakref

from typing import override, Any
from pydantic import Field, model_validator, ValidationInfo, computed_field, field_validator

from decimal import Decimal

from enum import StrEnum

from ..uid import Uid

from ..entity import IncrementingUidEntity
from ..instrument import Instrument


class TransactionType(StrEnum):
    # TODO: We might want to subclass transaction types for more specific behavior, e.g. AcquisitionTransaction vs DisposalTransaction ?
    BUY      = "buy"
    SELL     = "sell"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    FEE      = "fee"

    @override
    def __str__(self) -> str:
        return self.value

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class Transaction(IncrementingUidEntity):
    type           : TransactionType = Field(description="The type of transaction.")
    date           : datetime.date   = Field(description="The date of the transaction.")
    quantity       : Decimal         = Field(description="The quantity involved in the transaction.")
    consideration  : Decimal         = Field(description="The consideration amount for the transaction.")
    fees           : Decimal         = Field(default=Decimal(0), description="The fees associated with the transaction.")


    # MARK: Instrument
    @property
    def instrument(self) -> Instrument:
        from ..ledger import Ledger
        parent = self.instance_parent
        if not isinstance(parent, Ledger):
            raise ValueError(f"Transaction.instrument requires parent to be a Ledger, got {type(parent)}")
        return parent.instrument

    @computed_field(description="The UID of the associated instrument.")
    def instrument_uid(self) -> Uid:
        return self.instrument.uid

    @field_validator('instance_parent_weakref', mode='before')
    @classmethod
    def _validate_instance_parent_is_ledger(cls, value: Any) -> Any:
        from ..ledger import Ledger

        if value is None:
            return value

        parent = value() if isinstance(value, weakref.ref) else value
        if parent is not None and not isinstance(parent, Ledger):
            raise ValueError(f"Transaction.instance_parent must be a Ledger, got {type(value).__name__}.")

        return value


    # MARK: Uid
    #@classmethod
    #@override
    #def uid_namespace(cls, data : dict[str, Any] | None = None) -> str:
    #    """
    #    Returns the namespace for the UID.
    #    This can be overridden in subclasses to provide a custom namespace.
    #    """
    #    core_uid_namespace = super().uid_namespace(data)
    #    if data is None:
    #        return core_uid_namespace

    #    if (instrument_uid := data.get('instrument_uid', None)) is None:
    #        raise ValueError(f"{cls.__name__}.uid_namespace requires 'instrument_uid' in data to generate a UID namespace.")

    #    instrument = Instrument.by_uid(instrument_uid)
    #    if instrument is None:
    #        raise ValueError(f"{cls.__name__}.uid_namespace requires 'instrument_uid' to correspond to a valid Instrument to generate a UID namespace.")

    #    return f"{core_uid_namespace}-{instrument.instance_name}"