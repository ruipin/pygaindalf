# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, Any, override

from pydantic import model_validator
from pydantic_core import PydanticUseDefault

from ....util.helpers.empty_class import EmptyClass
from ..entity import Entity
from ..entity.instance_store import InstanceStoreEntityMixin
from .instrument_base import InstrumentBase
from .instrument_fields import InstrumentFields
from .instrument_journal import InstrumentJournal


if TYPE_CHECKING:
    from ..store import StringUidMapping
    from .instrument_proxy import InstrumentProxy  # noqa: F401


class Instrument(
    InstrumentBase,
    InstrumentFields if not TYPE_CHECKING else EmptyClass,
    InstanceStoreEntityMixin,
    Entity[InstrumentJournal, "InstrumentProxy"],
):
    # MARK: Instance Store Behaviour
    @classmethod
    def _get_isin_store(cls) -> StringUidMapping:
        return cls._get_entity_store().get_string_uid_mapping(f"{cls.__name__}_BY_ISIN")

    @classmethod
    def _get_ticket_store(cls) -> StringUidMapping:
        return cls._get_entity_store().get_string_uid_mapping(f"{cls.__name__}_BY_TICKER")

    @classmethod
    def instance(cls, isin: str | None = None, ticker: str | None = None) -> Instrument | None:
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
    def _instance_store_search(cls, **kwargs) -> Instrument | None:
        isin = kwargs.get("isin")
        ticker = kwargs.get("ticker")
        return cls.instance(isin=isin, ticker=ticker)

    @classmethod
    @override
    def _instance_store_add(cls, instance: Entity) -> None:
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

    # MARK: Model Validation
    @model_validator(mode="before")
    @classmethod
    def _validate_model_before(cls, values: Any) -> Any:
        """Validate the identifiers of the instrument.

        Ensures that at least one identifier (ISIN or ticker) is provided.
        """
        if values is None:
            raise PydanticUseDefault

        if isinstance(values, Instrument):
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

    # MARK: Instance Name
    @classmethod
    @override
    def calculate_instance_name_from_dict(cls, data: dict[str, Any]) -> str:
        if (identifier := data.get("isin")) is None and (identifier := data.get("ticker")) is None:
            msg = f"{cls.__name__} must have either 'isin' or 'ticker' field in the data to generate a name for the instance."
            raise ValueError(msg)
        return identifier

    @property
    @override
    def instance_name(self) -> str:
        return type(self).calculate_instance_name_from_dict(self.__dict__)
