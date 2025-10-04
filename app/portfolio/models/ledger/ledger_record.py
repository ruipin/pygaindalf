# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, Any, override

from pydantic import field_validator

from ....util.helpers.empty_class import empty_class
from ..entity import EntityRecord
from ..instrument import Instrument
from .ledger_impl import LedgerImpl
from .ledger_journal import LedgerJournal
from .ledger_schema import LedgerSchema


if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison


class LedgerRecord(
    LedgerImpl,
    LedgerSchema if not TYPE_CHECKING else empty_class(),
    EntityRecord[LedgerJournal],
    init=False,
    unsafe_hash=True,
):
    # MARK: Instrument
    @field_validator("instrument", mode="before")
    @classmethod
    def _validate_instrument(cls, value: Any) -> Instrument:
        if not isinstance(value, Instrument):
            msg = f"Expected 'instrument' to be an Instrument, got {type(value).__name__}."
            raise TypeError(msg)
        return value

    # MARK: Utilities
    @override
    def sort_key(self) -> SupportsRichComparison:
        return (self.instance_name, self.uid)
