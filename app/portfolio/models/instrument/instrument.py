# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, override

from ....util.helpers.empty_class import empty_class
from ..entity import Entity, InstanceStoreMixin
from .instrument_impl import InstrumentImpl
from .instrument_journal import InstrumentJournal
from .instrument_record import InstrumentRecord


if TYPE_CHECKING:
    from ..store import StringUidMapping


class Instrument(
    InstrumentImpl if TYPE_CHECKING else empty_class(),
    InstanceStoreMixin,
    Entity[InstrumentRecord, InstrumentJournal],
    init=False,
):
    # MARK: Instance Store Behaviour
    @classmethod
    def _get_isin_store(cls) -> StringUidMapping:
        return cls._get_entity_store().get_string_uid_mapping(f"{cls.__name__}_BY_ISIN")

    @classmethod
    def _get_ticket_store(cls) -> StringUidMapping:
        return cls._get_entity_store().get_string_uid_mapping(f"{cls.__name__}_BY_TICKER")

    @classmethod
    def instance(cls, isin: str | None = None, ticker: str | None = None) -> Self | None:
        if not isinstance(isin, (str, type(None))) or not isinstance(ticker, (str, type(None))):
            msg = f"Expected 'isin' and 'ticker' to be str or None, got {type(isin).__name__} and {type(ticker).__name__}."
            raise TypeError(msg)
        elif not isin and not ticker:
            return None

        # Check if an instance already exists for the given identifiers
        by_isin = cls._get_isin_store().get_entity(isin, fail=False) if isin else None
        by_ticker = cls._get_ticket_store().get_entity(ticker, fail=False) if ticker else None

        # Sanity check class instances
        if by_isin is not None and not isinstance(by_isin, cls):
            msg = f"Expected instance of {cls.__name__} for ISIN '{isin}', got {type(by_isin).__name__}."
            raise TypeError(msg)
        if by_ticker is not None and not isinstance(by_ticker, cls):
            msg = f"Expected instance of {cls.__name__} for ticker '{ticker}', got {type(by_ticker).__name__}."
            raise TypeError(msg)

        # Sanity check that the instruments match the identifiers
        if by_isin is not None and by_isin.isin != isin:
            msg = f"ISIN '{isin}' does not match existing instance with ISIN '{by_isin.isin}'."
            raise ValueError(msg)
        if by_ticker is not None and by_ticker.ticker != ticker:
            msg = f"Ticker '{ticker}' does not match existing instance with ticker '{by_ticker.ticker}'."
            raise ValueError(msg)

        # If both identifiers are provided, ensure they match
        # Return the existing instance if found
        if by_isin is not None and by_ticker is not None:
            if by_isin is not by_ticker:
                msg = f"Conflicting instances found for ISIN '{isin}' and ticker '{ticker}'."
                raise ValueError(msg)
            return by_isin
        elif by_isin is not None:
            return by_isin
        elif by_ticker is not None:
            return by_ticker
        else:
            return None

    @classmethod
    @override
    def _instance_store_search(cls, **kwargs) -> Self | None:
        isin = kwargs.get("isin")
        ticker = kwargs.get("ticker")
        return cls.instance(isin=isin, ticker=ticker)

    @classmethod
    @override
    def _instance_store_add(cls, instance: Self) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Add an instance to the store.

        This method is called when a new instance is created.
        """
        if not isinstance(instance, cls):
            msg = f"Expected an instance of {cls.__name__}, got {type(instance).__name__}."
            raise TypeError(msg)

        if instance.isin:
            cls._get_isin_store()[instance.isin] = instance.uid
        if instance.ticker:
            cls._get_ticket_store()[instance.ticker] = instance.uid

    # MARK: Instance Name
    @classmethod
    @override
    def calculate_instance_name_from_dict(cls, data: Mapping[str, Any]) -> str:
        if (identifier := data.get("isin")) is None and (identifier := data.get("ticker")) is None:
            msg = f"{cls.__name__} must have either 'isin' or 'ticker' field in the data to generate a name for the instance."
            raise ValueError(msg)
        return identifier


InstrumentRecord.register_entity_class(Instrument)
