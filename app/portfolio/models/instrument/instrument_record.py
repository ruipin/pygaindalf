# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, Any

from pydantic import model_validator
from pydantic_core import PydanticUseDefault

from ....util.helpers.empty_class import empty_class
from ..entity import EntityRecord
from .instrument_impl import InstrumentImpl
from .instrument_journal import InstrumentJournal
from .instrument_schema import InstrumentSchema


class InstrumentRecord(
    InstrumentImpl,
    InstrumentSchema if not TYPE_CHECKING else empty_class(),
    EntityRecord[InstrumentJournal],
    init=False,
    unsafe_hash=True,
):
    # MARK: Model Validation
    @model_validator(mode="before")
    @classmethod
    def _validate_model_before(cls, values: Any) -> Any:
        """Validate the identifiers of the instrument.

        Ensures that at least one identifier (ISIN or ticker) is provided.
        """
        if values is None:
            raise PydanticUseDefault

        if isinstance(values, InstrumentRecord):
            return values

        if not isinstance(values, dict):
            msg = f"Expected a dict or Instrument instance, got {type(values).__name__}."
            raise TypeError(msg)

        # Identifiers
        cls._validate_identifiers(values)

        return values

    @classmethod
    def _validate_identifiers(cls, values: dict[str, Any]) -> None:
        isin = values.get("isin")
        ticker = values.get("ticker")
        if not isin and not ticker:
            msg = "At least one identifier (ISIN or ticker) must be provided."
            raise ValueError(msg)
