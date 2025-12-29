# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import decimal

import pytest

from pydantic import BaseModel

from app.util.helpers.currency import Currency
from app.util.helpers.decimal_currency import DecimalCurrency


@pytest.mark.helpers
@pytest.mark.decimal
class TestDecimalCurrencyBasics:
    def test_zero_without_currency_allowed(self) -> None:
        value = DecimalCurrency("0")
        assert value == decimal.Decimal(0)
        assert value.currency is None
        assert str(value) == "0"

    def test_non_zero_requires_currency(self) -> None:
        with pytest.raises(ValueError, match="must have a currency specified for non-zero values"):
            _ = DecimalCurrency("1")

    def test_string_with_embedded_currency(self) -> None:
        value = DecimalCurrency("12.34 USD")
        assert value == decimal.Decimal("12.34")
        assert value.currency == Currency("USD")
        assert str(value) == "12.34 USD"

    def test_currency_argument_overrides_zero(self) -> None:
        value = DecimalCurrency("0", currency="EUR")
        assert value.currency == Currency("EUR")
        assert str(value) == "0 EUR"

    def test_currency_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="Currency mismatch"):
            _ = DecimalCurrency("10 USD", currency="EUR")


@pytest.mark.helpers
@pytest.mark.decimal
class TestDecimalCurrencyOperations:
    def test_addition_preserves_currency(self) -> None:
        a = DecimalCurrency("10", currency="USD")
        b = DecimalCurrency("2", currency="USD")
        c = a + b
        assert isinstance(c, DecimalCurrency)
        assert c == decimal.Decimal(12)
        assert c.currency == Currency("USD")

    def test_subtraction_preserves_currency(self) -> None:
        a = DecimalCurrency("10", currency="USD")
        b = DecimalCurrency("2", currency="USD")
        c = a - b
        assert isinstance(c, DecimalCurrency)
        assert c == decimal.Decimal(8)
        assert c.currency == Currency("USD")

    def test_addition_currency_mismatch_raises(self) -> None:
        a = DecimalCurrency("10", currency="USD")
        b = DecimalCurrency("2", currency="EUR")
        with pytest.raises(ValueError, match="Cannot add between DecimalCurrency with different currencies"):
            _ = a + b

    def test_operations_with_plain_decimal_propagate_currency(self) -> None:
        a = DecimalCurrency("10", currency="USD")
        b = decimal.Decimal(2)
        c = a + b
        assert isinstance(c, DecimalCurrency)
        assert c == decimal.Decimal(12)
        assert c.currency == Currency("USD")

    def test_multiplication_with_scalar_keeps_currency(self) -> None:
        a = DecimalCurrency("10", currency="USD")
        c = a * 2
        assert isinstance(c, DecimalCurrency)
        assert c == decimal.Decimal(20)
        assert c.currency == Currency("USD")

    def test_division_with_scalar_keeps_currency(self) -> None:
        a = DecimalCurrency("10", currency="USD")
        c = a / 4
        assert isinstance(c, DecimalCurrency)
        assert c.currency == Currency("USD")

    def test_comparisons_ignore_currency_but_require_match(self) -> None:
        a = DecimalCurrency("10", currency="USD")
        b = DecimalCurrency("10", currency="USD")
        assert a == b
        assert not (a < b)
        assert not (a > b)

    def test_comparisons_currency_mismatch_raise(self) -> None:
        a = DecimalCurrency("10", currency="USD")
        b = DecimalCurrency("10", currency="EUR")
        with pytest.raises(ValueError, match="Cannot add between DecimalCurrency with different currencies"):
            _ = a + b

        with pytest.raises(ValueError, match="Cannot lt DecimalCurrency with different currencies"):
            _ = a < b

        with pytest.raises(ValueError, match="Cannot gt DecimalCurrency with different currencies"):
            _ = a > b

    def test_all_comparisons_zero_without_currency(self) -> None:
        a = DecimalCurrency("0")
        b = DecimalCurrency("0")

        assert a == b
        assert not (a != b)  # noqa: SIM202
        assert not (a < b)
        assert not (a > b)
        assert a <= b
        assert a >= b

    def test_all_comparisons_with_currency(self) -> None:
        a = DecimalCurrency("10", currency="USD")
        b = DecimalCurrency("12", currency="USD")

        assert not (a == b)  # noqa: SIM201
        assert a != b
        assert a < b
        assert a <= b
        assert not (a > b)
        assert not (a >= b)

    def test_all_comparisons_currency_mismatch_non_zero(self) -> None:
        a = DecimalCurrency("10", currency="USD")
        b = DecimalCurrency("12", currency="EUR")

        with pytest.raises(ValueError, match="Cannot lt DecimalCurrency with different currencies"):
            _ = a < b

        with pytest.raises(ValueError, match="Cannot le DecimalCurrency with different currencies"):
            _ = a <= b

        with pytest.raises(ValueError, match="Cannot gt DecimalCurrency with different currencies"):
            _ = a > b

        with pytest.raises(ValueError, match="Cannot ge DecimalCurrency with different currencies"):
            _ = a >= b

    def test_all_comparisons_zero_none_vs_zero_currency(self) -> None:
        a = DecimalCurrency("0")
        b = DecimalCurrency("0", currency="USD")

        assert a == b
        assert not (a != b)  # noqa: SIM202
        assert not (a < b)
        assert not (a > b)
        assert a <= b
        assert a >= b

    def test_all_comparisons_zero_none_vs_zero_different_currencies(self) -> None:
        a = DecimalCurrency("0", currency="USD")
        b = DecimalCurrency("0", currency="EUR")

        assert a != b
        with pytest.raises(ValueError, match="Cannot lt DecimalCurrency with different currencies"):
            _ = a < b

        with pytest.raises(ValueError, match="Cannot le DecimalCurrency with different currencies"):
            _ = a <= b

        with pytest.raises(ValueError, match="Cannot gt DecimalCurrency with different currencies"):
            _ = a > b

        with pytest.raises(ValueError, match="Cannot ge DecimalCurrency with different currencies"):
            _ = a >= b


@pytest.mark.helpers
@pytest.mark.decimal
class TestDecimalCurrencyPydantic:
    class Model(BaseModel):
        amount: DecimalCurrency

    def test_pydantic_accepts_decimalcurrency(self) -> None:
        m = self.Model(amount=DecimalCurrency("1", currency="USD"))
        assert isinstance(m.amount, DecimalCurrency)
        assert m.amount.currency == Currency("USD")

    def test_pydantic_rejects_non_zero_without_currency(self) -> None:
        # Underlying DecimalCurrency constructor enforces currency for non-zero
        payload: dict[str, str] = {"amount": "1"}
        with pytest.raises(ValueError, match="must have a currency specified for non-zero values"):
            _ = self.Model(**payload)  # pyright: ignore[reportArgumentType]

    def test_pydantic_coerces_from_str_zero(self) -> None:
        payload: dict[str, str] = {"amount": "0"}
        m = self.Model(**payload)  # pyright: ignore[reportArgumentType]
        assert isinstance(m.amount, DecimalCurrency)
        assert m.amount == decimal.Decimal(0)
        assert m.amount.currency is None

    def test_pydantic_coerces_from_str_with_currency(self) -> None:
        payload: dict[str, str] = {"amount": "1.23 USD"}
        m = self.Model(**payload)  # pyright: ignore[reportArgumentType]
        assert isinstance(m.amount, DecimalCurrency)
        assert m.amount == decimal.Decimal("1.23")
        assert m.amount.currency == Currency("USD")

    def test_pydantic_serialization_to_str(self) -> None:
        m = self.Model(amount=DecimalCurrency("1.23", currency="USD"))
        data = m.model_dump()
        assert data["amount"] == "1.23 USD"

    def test_pydantic_json_serialization(self) -> None:
        m = self.Model(amount=DecimalCurrency("1.23", currency="USD"))
        json_str = m.model_dump_json()
        assert "1.23 USD" in json_str
