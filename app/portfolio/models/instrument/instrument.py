# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from pydantic import model_validator, Field
from pydantic_core import PydanticUseDefault
from typing import override, Any, TYPE_CHECKING

from ....util.helpers.empty_class import EmptyClass

from ..entity.instance_store import InstanceStoreEntityMixin
from ..entity import Entity
from ..store import StringUidMapping

from .instrument_fields import InstrumentFields
from .instrument_base import InstrumentBase
from .instrument_journal import InstrumentJournal

if TYPE_CHECKING:
    from .instrument_proxy import InstrumentProxy



class Instrument(
    InstrumentBase,
    InstrumentFields if not TYPE_CHECKING else EmptyClass,
    InstanceStoreEntityMixin,
    Entity[InstrumentJournal, 'InstrumentProxy']
):
    # MARK: Instance Store Behaviour
    @classmethod
    def _get_isin_store(cls) -> StringUidMapping:
        return cls._get_entity_store().get_string_uid_mapping(f"{cls.__name__}_BY_ISIN")

    @classmethod
    def _get_ticket_store(cls) -> StringUidMapping:
        return cls._get_entity_store().get_string_uid_mapping(f"{cls.__name__}_BY_TICKER")

    @classmethod
    def instance(cls, isin : str | None = None, ticker: str | None = None) -> Instrument | None:
        if not isinstance(isin, (str, type(None))) or not isinstance(ticker, (str, type(None))):
            raise TypeError(f"Expected 'isin' and 'ticker' to be str or None, got {type(isin).__name__} and {type(ticker).__name__}.")
        elif not isin and not ticker:
            return None

        # Check if an instance already exists for the given identifiers
        by_isin = cls._get_isin_store().get_entity(isin, fail=False) if isin else None
        by_ticker = cls._get_ticket_store().get_entity(ticker, fail=False) if ticker else None

        # Sanity check class instances
        if by_isin is not None and not isinstance(by_isin, cls):
            raise TypeError(f"Expected instance of {cls.__name__} for ISIN '{isin}', got {type(by_isin).__name__}.")
        if by_ticker is not None and not isinstance(by_ticker, cls):
            raise TypeError(f"Expected instance of {cls.__name__} for ticker '{ticker}', got {type(by_ticker).__name__}.")

        # Sanity check that the instruments match the identifiers
        if by_isin is not None and by_isin.isin != isin:
            raise ValueError(f"ISIN '{isin}' does not match existing instance with ISIN '{by_isin.isin}'.")
        if by_ticker is not None and by_ticker.ticker != ticker:
            raise ValueError(f"Ticker '{ticker}' does not match existing instance with ticker '{by_ticker.ticker}'.")

        # If both identifiers are provided, ensure they match
        # Return the existing instance if found
        if by_isin is not None and by_ticker is not None:
            if by_isin is not by_ticker:
                raise ValueError(f"Conflicting instances found for ISIN '{isin}' and ticker '{ticker}'.")
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
        isin = kwargs.get('isin', None)
        ticker = kwargs.get('ticker', None)
        return cls.instance(isin=isin, ticker=ticker)

    @classmethod
    @override
    def _instance_store_add(cls, instance: Entity) -> None:
        """
        Add an instance to the store.
        This method is called when a new instance is created.
        """
        if not isinstance(instance, cls):
            raise TypeError(f"Expected an instance of {cls.__name__}, got {type(instance).__name__}.")

        if instance.isin:
            cls._get_isin_store()[instance.isin] = instance.uid
        if instance.ticker:
            cls._get_ticket_store()[instance.ticker] = instance.uid


    # MARK: Model Validation
    @model_validator(mode='before')
    @classmethod
    def _validate_model_before(cls, values: Any) -> Any:
        """
        Validate the identifiers of the instrument.
        Ensures that at least one identifier (ISIN or ticker) is provided.
        """
        if values is None:
            raise PydanticUseDefault()

        if isinstance(values, Instrument):
            return values

        if not isinstance(values, dict):
            raise TypeError(f"Expected a dict or Instrument instance, got {type(values).__name__}.")

        # Identifiers
        cls._validate_identifiers(values)

        return values

    @classmethod
    def _validate_identifiers(cls, values: dict[str, Any]) -> None:
        isin   = values.get('isin'  , None)
        ticker = values.get('ticker', None)
        if not isin and not ticker:
            raise ValueError("At least one identifier (ISIN or ticker) must be provided.")




    # MARK: Instance Name
    @classmethod
    @override
    def calculate_instance_name_from_dict(cls, data : dict[str, Any]) -> str:
        if (identifier := data.get('isin', None)) is None and (identifier := data.get('ticker', None)) is None:
            raise ValueError(f"{cls.__name__} must have either 'isin' or 'ticker' field in the data to generate a name for the instance.")
        return identifier

    @property
    @override
    def instance_name(self) -> str:
        return type(self).calculate_instance_name_from_dict(self.__dict__)