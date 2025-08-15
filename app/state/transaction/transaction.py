# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override
from dataclasses import dataclass

from datetime import date

from decimal import Decimal

from enum import StrEnum


from ..models.entity import IncrementingUidEntity
from ..models.instrument import Instrument


class TransactionType(StrEnum):
    # TODO: We might want to subclass transaction types for more specific behavior, e.g. AcquisitionTransaction vs DisposalTransaction ?
    BUY      = "buy"
    SELL     = "sell"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    FEE      = "fee"


@dataclass
class Transaction(IncrementingUidEntity):
    instrument    : Instrument
    type          : TransactionType
    date          : date
    quantity      : Decimal
    consideration : Decimal
    fees          : Decimal

    @property
    @override
    def uid_namespace(self) -> str:
        """
        Returns the namespace for the UID.
        This can be overridden in subclasses to provide a custom namespace.
        """
        return f"{super().uid_namespace}-{self.instrument.instance_name}"