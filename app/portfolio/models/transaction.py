# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime

from typing import override, Any
from pydantic import Field, model_validator, ValidationInfo, computed_field

from decimal import Decimal

from enum import StrEnum

from ..models import Uid

from .entity import IncrementingUidEntity
from .instrument import Instrument


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
    instrument_uid : Uid             = Field(description="The UID of the instrument associated with this transaction.")
    type           : TransactionType = Field(description="The type of transaction.")
    date           : datetime.date   = Field(description="The date of the transaction.")
    quantity       : Decimal         = Field(description="The quantity involved in the transaction.")
    consideration  : Decimal         = Field(description="The consideration amount for the transaction.")
    fees           : Decimal         = Field(default=Decimal(0), description="The fees associated with the transaction.")


    # MARK: Instrument
    @model_validator(mode='after')
    def _validate_instrument_uid(self, info: ValidationInfo) -> 'Transaction':
        self.instrument # property access fails if the UID is invalid
        return self

    @computed_field(description="The instrument associated with this transaction.")
    @property
    def instrument(self) -> Instrument:
        if (instrument := Instrument.by_uid(self.instrument_uid)) is None:
            raise ValueError(f"Transaction.instrument_uid '{self.instrument_uid}' does not correspond to a valid Instrument.")
        return instrument

    @instrument.setter
    def instrument(self, value : Instrument) -> None:
        self.instrument_uid = value.uid


    # MARK: Uid
    @classmethod
    @override
    def uid_namespace(cls, data : dict[str, Any] | None = None) -> str:
        """
        Returns the namespace for the UID.
        This can be overridden in subclasses to provide a custom namespace.
        """
        if data is None:
            raise ValueError(f"{cls.__name__}.uid_namespace requires data to generate a UID namespace.")

        core_uid_namespace = super().uid_namespace(data)

        if (instrument_uid := data.get('instrument_uid', None)) is None:
            raise ValueError(f"{cls.__name__}.uid_namespace requires 'instrument_uid' in data to generate a UID namespace.")

        instrument = Instrument.by_uid(instrument_uid)
        if instrument is None:
            raise ValueError(f"{cls.__name__}.uid_namespace requires 'instrument_uid' to correspond to a valid Instrument to generate a UID namespace.")

        return f"{core_uid_namespace}-{instrument.instance_name}"