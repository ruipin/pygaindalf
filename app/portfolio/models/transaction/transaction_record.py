# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from decimal import Decimal
from typing import TYPE_CHECKING, override

from pydantic import field_validator

from ....util.helpers.decimal_currency import DecimalCurrency
from ..entity import EntityRecord
from .transaction_impl import TransactionImpl
from .transaction_journal import TransactionJournal
from .transaction_schema import TransactionSchema


if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison


class TransactionRecord(
    TransactionImpl,
    EntityRecord[TransactionJournal],
    TransactionSchema,
    init=False,
    unsafe_hash=True,
):
    # MARK: Model Validation
    @field_validator("quantity", mode="after")
    def validate_quantity(cls, quantity: Decimal) -> Decimal:
        if quantity <= 0:
            msg = f"Transaction quantity must be positive, got {quantity}."
            raise ValueError(msg)

        return quantity

    @field_validator("consideration", mode="after")
    def validate_consideration(cls, consideration: DecimalCurrency) -> DecimalCurrency:
        if consideration.currency is None:
            msg = "Transaction consideration must have a valid currency."
            raise ValueError(msg)
        return consideration

    # MARK: Utilities
    @override
    def sort_key(self) -> SupportsRichComparison:
        return (self.date, 0 if self.type.trade else 1, self.uid)
