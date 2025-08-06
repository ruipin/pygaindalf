import decimal
import pytest
from app.util.helpers.decimal import DecimalFactory, DecimalConfig, DecimalRounding, DecimalSignals

@pytest.mark.helpers
@pytest.mark.decimal
class TestDecimalFactory:
    def test_default_config(self):
        factory = DecimalFactory()
        assert factory.config.precision == 9
        assert factory.config.rounding == DecimalRounding.HALF_DOWN
        assert factory.config.traps is not None
        assert factory.config.traps[DecimalSignals.DIVISION_BY_ZERO] is True
        assert factory.context.prec == 9
        assert factory.context.rounding == decimal.ROUND_HALF_DOWN

    def test_configure_with_kwargs(self):
        factory = DecimalFactory()
        factory.configure(precision=5, rounding=DecimalRounding.UP)
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
        factory = DecimalFactory()
        with pytest.raises(ValueError):
            factory.configure(config, precision=4)

    def test_apply_context(self):
        factory = DecimalFactory(None, precision=4)
        factory.apply_context()
        assert decimal.getcontext().prec == 4

    def test_with_context(self):
        factory = DecimalFactory(None, precision=6)
        with factory.with_context():
            assert decimal.getcontext().prec == 6
        # After context, should revert to default
        assert decimal.getcontext().prec != 6

    def test_call(self):
        factory = DecimalFactory(None, precision=3)
        d = factory('1.23456')
        assert isinstance(d, decimal.Decimal)
        assert str(d) == '1.23456'
