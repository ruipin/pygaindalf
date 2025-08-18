# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override, Any
from pydantic import Field

from datetime import date

from decimal import Decimal

from enum import StrEnum


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
    instrument    : Instrument = Field(json_schema_extra={'hierarchical': False})
    type          : TransactionType
    date          : date
    quantity      : Decimal
    consideration : Decimal
    fees          : Decimal

    @classmethod
    @override
    def uid_namespace(cls, data : dict[str, Any]) -> str:
        """
        Returns the namespace for the UID.
        This can be overridden in subclasses to provide a custom namespace.
        """
        core_uid_namespace = super().uid_namespace(data)

        if (instrument := data.get('instrument', None)) is None:
            raise ValueError(f"{cls.__name__} must have an 'instrument' field in the data to generate a UID namespace.")
        instrument_name = Instrument.calculate_instance_name_from_arbitrary_data(instrument)

        return f"{core_uid_namespace}-{instrument_name}"