# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import decimal

import pytest

from app.util.helpers.decimal import DecimalConfig, DecimalFactory, DecimalRounding, DecimalSignals


@pytest.mark.helpers
@pytest.mark.decimal
class TestDecimalFactory:
    def test_default_config(self):
        factory = DecimalFactory()

        assert factory.config.precision == DecimalConfig.model_fields["precision"].default_factory.default  # pyright: ignore[reportFunctionMemberAccess, reportOptionalMemberAccess]
        assert factory.config.rounding == DecimalConfig.model_fields["rounding"].default_factory.default  # pyright: ignore[reportFunctionMemberAccess, reportOptionalMemberAccess]
        assert factory.config.traps is not None

        for trap in DecimalSignals:
            value = factory.config.traps.get(trap)
            if trap in (DecimalSignals.INEXACT, DecimalSignals.ROUNDED):
                assert value is False
            else:
                assert value is True

        assert factory.context.prec == DecimalConfig.model_fields["precision"].default_factory.default  # pyright: ignore[reportFunctionMemberAccess, reportOptionalMemberAccess]
        assert factory.context.rounding == DecimalConfig.model_fields["rounding"].default_factory.default.value  # pyright: ignore[reportFunctionMemberAccess, reportOptionalMemberAccess]

    def test_configure_with_kwargs(self):
        factory = DecimalFactory(precision=5, rounding=DecimalRounding.UP)
        assert factory.config.precision == 5
        assert factory.config.rounding == DecimalRounding.UP
        assert factory.context.prec == 5
        assert factory.context.rounding == decimal.ROUND_UP

    def test_configure_with_config(self):
        config = DecimalConfig(precision=7, rounding=DecimalRounding.FLOOR)
        factory = DecimalFactory(config)
        assert factory.config.precision == 7
        assert factory.config.rounding == DecimalRounding.FLOOR
        assert factory.context.prec == 7
        assert factory.context.rounding == decimal.ROUND_FLOOR

    def test_configure_raises_on_both(self):
        config = DecimalConfig(precision=3)
        with pytest.raises(ValueError, match=r"Either provide a decimal config or keyword arguments, not both."):
            _ = DecimalFactory(config, precision=5)

    def test_apply_context(self):
        factory = DecimalFactory(precision=4)
        factory.apply_context()
        assert decimal.getcontext().prec == 4

    def test_with_context(self):
        factory = DecimalFactory(precision=6)
        with factory.context_manager():
            assert decimal.getcontext().prec == 6
        # After context, should revert to default
        assert decimal.getcontext().prec != 6

    def test_call(self):
        factory = DecimalFactory(precision=3)
        d = factory("1.23456")
        assert isinstance(d, decimal.Decimal)
        assert str(d) == "1.23456"
