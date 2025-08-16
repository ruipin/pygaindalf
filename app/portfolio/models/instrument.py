# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from . import AutomaticNamedEntity
from .instance_store import InstanceStoreModelMixin

from pydantic import Field, ValidatorFunctionWrapHandler, model_validator, PrivateAttr, field_validator, ValidationInfo, TypeAdapter
from pydantic_core import PydanticUseDefault
from typing import override, Any, ClassVar, Self

from iso4217 import Currency


class Instrument(InstanceStoreModelMixin, AutomaticNamedEntity):
    # MARK: Fields
    isin     : str | None = Field(default=None, min_length=1, description="International Securities Identification Number (ISIN) of the instrument.")
    ticker   : str | None = Field(default=None, min_length=1, description="Ticker symbol of the instrument, used for trading and identification.")
    currency : Currency   = Field(description="The currency in which the instrument is denominated.")


    # MARK: Instance Store Behaviour
    BY_ISIN   : 'ClassVar[dict[str, Instrument]]' = dict()
    BY_TICKER : 'ClassVar[dict[str, Instrument]]' = dict()

    @classmethod
    def instance(cls, isin : str | None = None, ticker: str | None = None) -> 'Instrument | None':
        if not isinstance(isin, (str, type(None))) or not isinstance(ticker, (str, type(None))):
            raise TypeError(f"Expected 'isin' and 'ticker' to be str or None, got {type(isin).__name__} and {type(ticker).__name__}.")
        elif not isin and not ticker:
            return None

        # Check if an instance already exists for the given identifiers
        by_isin = cls.BY_ISIN.get(isin, None) if isin else None
        by_ticker = cls.BY_TICKER.get(ticker, None) if ticker else None

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
    def _instance_store_search(cls, **kwargs) -> 'Instrument | None':
        isin = kwargs.get('isin', None)
        ticker = kwargs.get('ticker', None)
        return cls.instance(isin=isin, ticker=ticker)

    @classmethod
    @override
    def _instance_store_add(cls, instance: InstanceStoreModelMixin) -> None:
        """
        Add an instance to the store.
        This method is called when a new instance is created.
        """
        if not isinstance(instance, cls):
            raise TypeError(f"Expected an instance of {cls.__name__}, got {type(instance).__name__}.")

        if instance.isin:
            cls.BY_ISIN[instance.isin] = instance
        if instance.ticker:
            cls.BY_TICKER[instance.ticker] = instance



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
        if (identifier := data.get('isin', None) or data.get('ticker', None)) is None:
            raise ValueError(f"{cls.__name__} must have either 'isin' or 'ticker' field in the data to generate a name for the instance.")
        return identifier

    @property
    @override
    def instance_name(self) -> str:
        return self.__class__.calculate_instance_name_from_dict(self.__dict__)