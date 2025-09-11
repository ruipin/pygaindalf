# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime
import weakref

from typing import override, Any, TYPE_CHECKING
from pydantic import Field, computed_field, field_validator

from decimal import Decimal

if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison

from ..uid import Uid

from ..entity import IncrementingUidEntity
from ..instrument.instrument import Instrument

from .transaction_journal import TransactionJournal
from .transaction_type import TransactionType



class Transaction(IncrementingUidEntity[TransactionJournal]):
    @classmethod
    @override
    def get_journal_class(cls) -> type[TransactionJournal]:
        return TransactionJournal


    # MARK: Fields
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


    # MARK: Utilities
    @override
    def sort_key(self) -> SupportsRichComparison:
        return (self.date, self.uid)