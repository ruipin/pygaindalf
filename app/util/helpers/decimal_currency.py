# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import decimal
import functools
import inspect
import itertools
import re

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Self, override

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from .currency import Currency


class DecimalCurrency(decimal.Decimal):
    CURRENCY_REGEX = re.compile(r"^\s*([-+]?\d*\.?\d+)\s*([A-Z]{3})\s*$")

    currency: Currency | None

    @classmethod
    def get_regex_match(cls, value: str) -> re.Match | None:
        return cls.CURRENCY_REGEX.match(value)

    @staticmethod
    def _get_op_debug_name(fname: str) -> str:
        return fname.removeprefix("__").removesuffix("__")

    @classmethod
    def _copy_decimal_method(cls, fname: str, fn: Callable) -> None:
        @functools.wraps(fn)
        def _wrapper(self: DecimalCurrency, *args, **kwargs) -> Any:
            currency = getattr(self, "currency", None)

            # Loop through all params and sanity check any decimals
            for arg in itertools.chain(args, kwargs.values()):
                if isinstance(arg, DecimalCurrency):
                    if currency is None:
                        currency = arg.currency
                    elif currency != arg.currency:
                        msg = f"Cannot {cls._get_op_debug_name(fn.__name__)} between DecimalCurrency with different currencies: {currency} and {arg.currency}"
                        raise ValueError(msg)

            # Call the original method
            spr = getattr(decimal.Decimal, fname)
            result = spr(self, *args, **kwargs)

            # Sanity check: Result should never be DecimalCurrency
            if isinstance(result, DecimalCurrency):
                msg = f"Wrapped Decimal method {fname} should not return DecimalCurrency instances"
                raise TypeError(msg)
            # If result is not Decimal, return as is
            elif not isinstance(result, decimal.Decimal):
                return result
            # Otherwise, validate and convert to DecimalCurrency
            else:
                if currency is None and not result.is_zero():
                    msg = "DecimalCurrency must have a currency specified for non-zero values"
                    raise ValueError(msg)

                return DecimalCurrency(result, currency=currency)

        setattr(cls, fname, _wrapper)

    @classmethod
    def _copy_decimal_methods(cls) -> None:
        for fname, fn in inspect.getmembers_static(decimal.Decimal, predicate=inspect.isroutine):
            if fname in cls.__dict__ or fname in (
                "__setattr__",
                "__getattr__",
                "__getattribute__",
                "__new__",
                "__init__",
                "__deepcopy__",
                "__copy__",
                "__eq__",
                "__ne__",
            ):
                continue

            cls._copy_decimal_method(fname, fn)

    def __new__(
        cls,
        value: decimal._DecimalNew = "0",
        currency: Currency | str | None = None,
        *,
        default_currency: Currency | str | None = None,
        context: decimal.Context | None = None,
    ) -> Self:
        if currency is not None and not isinstance(currency, Currency):
            currency = Currency(currency)

        if isinstance(value, str):
            match = cls.CURRENCY_REGEX.match(value)
            if match:
                value, _currency = match.groups()
                _currency = Currency(_currency)

                if currency is not None and currency != _currency:
                    msg = f"Currency mismatch between value string '{_currency}' and provided currency '{currency}'"
                    raise ValueError(msg)
                currency = _currency

        inst = super().__new__(cls, value, context=context)

        if currency is None:
            if default_currency is not None:
                currency = default_currency

        if currency is None and not inst.is_zero():
            msg = "DecimalCurrency must have a currency specified for non-zero values"
            raise ValueError(msg)

        inst.currency = Currency(currency) if currency is not None else None

        return inst

    def decimal(self) -> decimal.Decimal:
        return decimal.Decimal(self)

    def convert(self, target: Currency | str, rate: decimal.Decimal) -> DecimalCurrency:
        target = Currency(target)

        if self.currency == target:
            return self

        converted_value = self.decimal() * rate
        return DecimalCurrency(converted_value, currency=target)

    def round(self, ndigits: int | None = None) -> DecimalCurrency:
        if ndigits is None:
            return self
        rounded_value = round(self, ndigits)
        return DecimalCurrency(rounded_value, currency=self.currency)

    # MARK: Pydantic
    @classmethod
    def __get_pydantic_core_schema__(cls, source: type[Any], handler: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.no_info_plain_validator_function(
            function=cls.validate_and_coerce,
            json_schema_input_schema=core_schema.decimal_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                function=cls.serialize,
            ),
        )

    @classmethod
    def validate_and_coerce(cls, value: Any) -> DecimalCurrency:
        if isinstance(value, DecimalCurrency):
            return value
        elif isinstance(value, (decimal.Decimal, str, int, float)):
            return cls(value)
        else:
            msg = f"Cannot coerce value of type {type(value).__name__} to DecimalCurrency"
            raise TypeError(msg)

    @classmethod
    def serialize(cls, value: DecimalCurrency) -> str:
        return str(value)

    # MARK: Comparison
    @override
    def __hash__(self) -> int:
        return hash((super().__hash__(), self.currency))

    @override
    def __eq__(self, other: object) -> bool:
        if isinstance(other, DecimalCurrency):
            if self.currency is None or other.currency is None:
                pass
            elif self.currency != other.currency:
                return False

        return bool(super().__eq__(other))

    @override
    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def _compare_currency_and_call_super(self, other: Any, op: Callable[[Any], Any]) -> bool:
        if isinstance(other, DecimalCurrency):
            if self.currency is None or other.currency is None:
                pass
            elif self.currency != other.currency:
                msg = f"Cannot {self._get_op_debug_name(op.__name__)} DecimalCurrency with different currencies: {self.currency} and {other.currency}"
                raise ValueError(msg)

        return bool(op(other))

    @override
    def __lt__(self, other: Any) -> bool:  # type: ignore[override]
        return self._compare_currency_and_call_super(other, super().__lt__)

    @override
    def __le__(self, other: Any) -> bool:  # type: ignore[override]
        return self._compare_currency_and_call_super(other, super().__le__)

    @override
    def __gt__(self, other: Any) -> bool:  # type: ignore[override]
        return self._compare_currency_and_call_super(other, super().__gt__)

    @override
    def __ge__(self, other: Any) -> bool:  # type: ignore[override]
        return self._compare_currency_and_call_super(other, super().__ge__)

    # MARK: Utilities
    @override
    def __str__(self) -> str:
        spr = super().__str__()
        if self.currency is None:
            return spr
        else:
            return f"{spr} {self.currency.code}"

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}({self!s})"

    # MARK: Type hints
    if TYPE_CHECKING:

        @override
        def compare(self, other: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def __abs__(self) -> DecimalCurrency: ...
        @override
        def __add__(self, value: decimal._Decimal, /) -> DecimalCurrency: ...
        @override
        def __floordiv__(self, value: decimal._Decimal, /) -> DecimalCurrency: ...
        @override
        def __mod__(self, value: decimal._Decimal, /) -> DecimalCurrency: ...
        @override
        def __mul__(self, value: decimal._Decimal, /) -> DecimalCurrency: ...
        @override
        def __neg__(self) -> DecimalCurrency: ...
        @override
        def __pos__(self) -> DecimalCurrency: ...
        @override
        def __pow__(self, value: decimal._Decimal, mod: decimal._Decimal | None = None, /) -> DecimalCurrency: ...
        @override
        def __radd__(self, value: decimal._Decimal, /) -> DecimalCurrency: ...
        @override
        def __rfloordiv__(self, value: decimal._Decimal, /) -> DecimalCurrency: ...
        @override
        def __rmod__(self, value: decimal._Decimal, /) -> DecimalCurrency: ...
        @override
        def __rmul__(self, value: decimal._Decimal, /) -> DecimalCurrency: ...
        @override
        def __rsub__(self, value: decimal._Decimal, /) -> DecimalCurrency: ...
        @override
        def __rtruediv__(self, value: decimal._Decimal, /) -> DecimalCurrency: ...
        @override
        def __sub__(self, value: decimal._Decimal, /) -> DecimalCurrency: ...
        @override
        def __truediv__(self, value: decimal._Decimal, /) -> DecimalCurrency: ...
        @override
        def remainder_near(self, other: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def conjugate(self) -> DecimalCurrency: ...
        @override
        def fma(self, other: decimal._Decimal, third: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def __rpow__(self, value: decimal._Decimal, mod: decimal.Context | None = None, /) -> DecimalCurrency: ...
        @override
        def normalize(self, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def quantize(self, exp: decimal._Decimal, rounding: str | None = None, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def to_integral_exact(self, rounding: str | None = None, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def to_integral_value(self, rounding: str | None = None, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def to_integral(self, rounding: str | None = None, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def sqrt(self, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def max(self, other: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def min(self, other: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def canonical(self) -> DecimalCurrency: ...
        @override
        def compare_signal(self, other: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def compare_total(self, other: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def compare_total_mag(self, other: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def copy_abs(self) -> DecimalCurrency: ...
        @override
        def copy_negate(self) -> DecimalCurrency: ...
        @override
        def copy_sign(self, other: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def exp(self, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def ln(self, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def log10(self, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def logb(self, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def logical_and(self, other: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def logical_invert(self, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def logical_or(self, other: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def logical_xor(self, other: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def max_mag(self, other: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def min_mag(self, other: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def next_minus(self, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def next_plus(self, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def next_toward(self, other: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def radix(self) -> DecimalCurrency: ...
        @override
        def rotate(self, other: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def scaleb(self, other: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def shift(self, other: decimal._Decimal, context: decimal.Context | None = None) -> DecimalCurrency: ...
        @override
        def __copy__(self) -> Self: ...
        @override
        def __deepcopy__(self, memo: Any, /) -> Self: ...


DecimalCurrency._copy_decimal_methods()  # noqa: SLF001
