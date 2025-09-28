# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import decimal

from enum import Enum
from pydantic import ConfigDict, PositiveInt, field_validator
from pydantic_core import PydanticUseDefault
from typing import override, Any

from ..config import BaseConfigModel
from ..config.inherit import FieldInherit


# MARK: Enumerations
class DecimalRounding(Enum):
    """
    Enum for Decimal rounding modes.
    This is useful for specifying how decimal numbers should be rounded in financial calculations.
    """
    CEILING   = decimal.ROUND_CEILING
    DOWN      = decimal.ROUND_DOWN
    FLOOR     = decimal.ROUND_FLOOR
    HALF_DOWN = decimal.ROUND_HALF_DOWN
    HALF_EVEN = decimal.ROUND_HALF_EVEN
    HALF_UP   = decimal.ROUND_HALF_UP
    UP        = decimal.ROUND_UP
    UP05      = decimal.ROUND_05UP

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.name}"


class DecimalSignals(Enum):
    """
    Enum for Decimal signals.
    This is useful for specifying how decimal numbers should handle special cases like NaN or Infinity.
    """
    CLAMPED          = decimal.Clamped
    DIVISION_BY_ZERO = decimal.DivisionByZero
    INEXACT          = decimal.Inexact
    INVALID_OP       = decimal.InvalidOperation
    OVERFLOW         = decimal.Overflow
    ROUNDED          = decimal.Rounded
    SUBNORMAL        = decimal.Subnormal
    UNDERFLOW        = decimal.Underflow
    FLOAT_OP         = decimal.FloatOperation

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.name}"


# MARK: Configuration
class DecimalConfig(BaseConfigModel):
    precision : PositiveInt                       = FieldInherit(32)
    rounding  : DecimalRounding                   = FieldInherit(DecimalRounding.HALF_DOWN)
    traps     : dict[DecimalSignals, bool]        = FieldInherit({ signal: True for signal in DecimalSignals })
    emin      : int                        | None = FieldInherit(None)
    emax      : int                        | None = FieldInherit(None)
    capitals  : bool                       | None = FieldInherit(None)
    clamp     : bool                       | None = FieldInherit(True)

    @field_validator('rounding', mode='before')
    @classmethod
    def validate_rounding(cls, value: str | DecimalRounding | None) -> DecimalRounding | str | None:
        if value is None:
            return None
        if isinstance(value, DecimalRounding):
            return value
        try:
            return DecimalRounding[value]
        except KeyError:
            return value

    @field_validator('traps', mode='before')
    @classmethod
    def validate_traps(cls, value: Any) -> dict[DecimalSignals, bool]:
        if value is None:
            raise PydanticUseDefault()
        if not isinstance(value, dict):
            raise TypeError(f"Expected a dictionary for traps, got {type(value).__name__}")

        new_signals = {}

        for key, enabled in value.items():
            if isinstance(key, str):
                try:
                    key = DecimalSignals[key]
                except KeyError:
                    raise ValueError(f"Invalid signal name: {key}")

            new_signals[key] = enabled
        return new_signals

    @field_validator('traps', mode='after')
    @classmethod
    def add_missing_traps(cls, value: dict[DecimalSignals, bool]) -> dict[DecimalSignals, bool]:
        # Ensure all DecimalSignals are present in the traps dictionary and default to True
        for signal in DecimalSignals:
            if signal not in value:
                value[signal] = True
        return value


    @property
    def rounding_value(self) -> str | None:
        if self.rounding is None:
            return None
        return self.rounding.value

    @property
    def traps_value(self) -> list[type] | None:
        if self.traps is None:
            return None

        return [
            signal.value if isinstance(signal, DecimalSignals) else signal
            for signal, enabled in self.traps.items() if enabled
        ]

    @property
    def kwargs(self) -> dict[str, Any]:
        return {
            'prec'    : self.precision,
            'rounding': self.rounding_value,
            'traps'   : self.traps_value,
            'Emin'    : self.emin,
            'Emax'    : self.emax,
            'capitals': self.capitals,
            'clamp'   : self.clamp
        }


# MARK: Factory
class DecimalFactory:
    """
    Factory function to create a Decimal class with specified context settings
    This is useful for financial calculations where precision is crucial.
    """
    def __init__(self, config : DecimalConfig | None = None, **kwargs) -> None:
        super().__init__()

        if config is not None and kwargs:
            raise ValueError("Either provide a decimal config or keyword arguments, not both.")
        elif config is None:
            config = DecimalConfig.model_validate(kwargs)

        self.config = config
        self.context = decimal.Context(**self.config.kwargs)

    def apply_context(self) -> None:
        decimal.setcontext(self.context)

    def context_manager(self):
        return decimal.localcontext(self.context)

    def __call__(self, value: str | int | float | decimal.Decimal) -> decimal.Decimal:
        """
        Create a Decimal instance with the current context settings.
        This is useful for creating Decimal objects with the specified precision and rounding.
        """
        return decimal.Decimal(value, context=self.context)

