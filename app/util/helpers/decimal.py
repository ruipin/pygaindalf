# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import decimal

from enum import Enum
from pydantic import ConfigDict, PositiveInt, field_validator
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
        return self.name


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
        return self.name


# MARK: Configuration
class DecimalConfig(BaseConfigModel):
    precision : PositiveInt                | None = FieldInherit(9)
    rounding  : DecimalRounding            | None = FieldInherit(DecimalRounding.HALF_DOWN)
    traps     : dict[DecimalSignals, bool] | None = FieldInherit({ signal: True for signal in DecimalSignals })
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

    @property
    def rounding_value(self) -> str | None:
        if self.rounding is None:
            return None
        return self.rounding.value

    @property
    def traps_value(self) -> dict[type, bool] | None:
        if self.traps is None:
            return None
        return {key.value if isinstance(key, DecimalSignals) else key: value for key, value in self.traps.items()}

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

class DecimalConfigUnfrozen(DecimalConfig):
    model_config = ConfigDict(frozen=False)


# MARK: Factory
class DecimalFactory:
    """
    Factory function to create a Decimal class with specified context settings
    This is useful for financial calculations where precision is crucial.
    """

    def __init__(self, *args, **kwargs):
        self.configure(*args, **kwargs)

    def configure(self, config : DecimalConfig | None = None, **kwargs) -> DecimalConfig:
        if config is not None and kwargs:
            raise ValueError("Either provide a decimal config or keyword arguments, not both.")
        if config is not None:
            config = DecimalConfigUnfrozen.model_validate(config.model_dump())
        elif getattr(self, 'config', None) is None:
            config = DecimalConfigUnfrozen.model_validate(kwargs)
        else:
            config = self.config.model_copy(update=kwargs)

        self.config = config
        self._configure_context()

        return self.config

    def _configure_context(self) -> None:
        if not hasattr(self, 'context'):
            self.context = decimal.Context(
                prec     = self.config.precision,
                rounding = self.config.rounding_value,
                traps    = self.config.traps_value,
                Emin     = self.config.emin,
                Emax     = self.config.emax,
                capitals = self.config.capitals,
                clamp    = self.config.clamp
            )
        else:
            for key, value in self.config.kwargs.items():
                current = getattr(self.context, key, None)
                if value is not None and value != current:
                    setattr(self.context, key, value)

    def apply_context(self) -> None:
        decimal.setcontext(self.context)

    def with_context(self):
        return decimal.localcontext(self.context)

    def __call__(self, value: str | int | float | decimal.Decimal) -> decimal.Decimal:
        """
        Create a Decimal instance with the current context settings.
        This is useful for creating Decimal objects with the specified precision and rounding.
        """
        return decimal.Decimal(value, context=self.context)

