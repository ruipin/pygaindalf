# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from typing import TYPE_CHECKING

from iso4217 import Currency

from ....util.helpers.empty_class import empty_class
from ..entity import EntityImpl
from .transaction_schema import TransactionSchema


if TYPE_CHECKING:
    from decimal import Decimal

    from ....util.helpers.decimal_currency import DecimalCurrency
    from ..annotation.forex import ForexAnnotation
    from ..annotation.s104 import S104HoldingsAnnotation, S104PoolAnnotation
    from ..instrument import Instrument


# TODO: Move to some common location e.g. in a S104 extension module
S104_CURRENCY = Currency("GBP")


class TransactionImpl(
    EntityImpl,
    TransactionSchema if TYPE_CHECKING else empty_class(),
    metaclass=ABCMeta,
):
    # MARK: Instrument
    @property
    def instrument_or_none(self) -> Instrument | None:
        from ..ledger import Ledger

        parent = self.entity.instance_parent
        if parent is None or not isinstance(parent, Ledger):
            return None

        return parent.instrument

    @property
    def instrument(self) -> Instrument:
        if (instrument := self.instrument_or_none) is None:
            msg = "Transaction's instrument requested but not found. This may indicate data corruption."
            raise ValueError(msg)
        return instrument

    # MARK: Currency
    @property
    def currency(self) -> Currency:
        currency = self.consideration.currency
        assert currency is not None, "Transaction consideration currency should have been validated already."
        return currency

    # MARK: Forex
    @property
    def forex_annotation_or_none(self) -> ForexAnnotation | None:
        from ..annotation.forex import ForexAnnotation

        return ForexAnnotation.get(self.entity)

    @property
    def forex_annotation(self) -> ForexAnnotation:
        if (ann := self.forex_annotation_or_none) is None:
            msg = "Forex annotation requested but not found. Please ensure you have run a forex annotator."
            raise ValueError(msg)
        return ann

    def get_exchange_rate(self, currency: Currency | str, *, use_forex_annotation: bool = True) -> Decimal:
        currency = Currency(currency)

        if currency == self.currency:
            return self.decimal(1)

        if use_forex_annotation and (ann := self.forex_annotation_or_none) is not None:
            return ann.get_exchange_rate(currency)

        return self.forex_provider.get_daily_rate(source=self.currency, target=currency, date=self.date)

    # MARK: Consideration
    # TODO: Allow requesting after fees
    def get_consideration(self, *, currency: Currency | str | None = None, use_forex_annotation: bool = True) -> DecimalCurrency:
        currency = Currency(currency) if currency is not None else self.currency

        if currency is None or currency == self.currency:
            return self.consideration

        if use_forex_annotation and (ann := self.forex_annotation_or_none) is not None:
            return ann.get_consideration(currency)

        return self.forex_provider.convert_currency(amount=self.consideration, source=self.currency, target=currency, date=self.date)

    def get_partial_consideration(self, quantity: Decimal, *, currency: Currency | str | None = None) -> DecimalCurrency:
        if self.quantity == 0:
            msg = "Cannot calculate partial consideration for transaction with zero quantity"
            raise ValueError(msg)

        if self.quantity == quantity:
            result = self.consideration
        elif quantity == 1:
            result = self.unit_consideration
        else:
            result = self.unit_consideration * quantity

        if currency is not None:
            currency = Currency(currency)
            if result.currency != currency:
                rate = self.get_exchange_rate(currency)
                result = result.convert(target=currency, rate=rate)
                assert result.currency == currency, f"Currency conversion failed, got {result.currency}."

        return result

    def get_unit_consideration(self, *, currency: Currency | str | None = None) -> DecimalCurrency:
        if self.quantity == 0:
            msg = "Cannot calculate unit consideration for transaction with zero quantity"
            raise ValueError(msg)

        total_consideration = self.get_consideration(currency=currency)
        return total_consideration / self.quantity

    @property
    def unit_consideration(self) -> DecimalCurrency:
        return self.get_unit_consideration()

    # MARK: Fees
    def get_fees(self, *, currency: Currency | str | None) -> DecimalCurrency:
        if self.fees == 0:
            return self.decimal.currency(0, currency=currency)

        currency = Currency(currency) if currency is not None else self.fees.currency
        if currency == self.fees.currency:
            return self.fees
        elif currency is None:
            msg = "Currency should not be None here."
            raise ValueError(msg)
        else:
            rate = self.get_exchange_rate(currency)
            return self.fees.convert(target=currency, rate=rate)

    def get_unit_fees(self, *, currency: Currency | str | None = None) -> DecimalCurrency:
        if self.quantity == 0:
            msg = "Cannot calculate unit fees for transaction with zero quantity"
            raise ValueError(msg)

        total_fees = self.get_fees(currency=currency)
        return total_fees / self.quantity

    @property
    def unit_fees(self) -> DecimalCurrency:
        return self.get_unit_fees()

    def get_partial_fees(self, quantity: Decimal, *, currency: Currency | str | None = None) -> DecimalCurrency:
        if self.quantity == 0:
            msg = "Cannot calculate partial fees for transaction with zero quantity"
            raise ValueError(msg)

        if quantity == self.quantity:
            return self.get_fees(currency=currency)

        unit_fees = self.get_unit_fees(currency=currency)
        return unit_fees * quantity

    # MARK: Discount
    def get_discount(self, *, currency: Currency | str | None = None) -> DecimalCurrency:
        if currency is None or currency == self.discount.currency:
            return self.discount

        if self.discount == 0:
            return self.decimal.currency(0, currency=currency)

        rate = self.get_exchange_rate(currency)
        return self.discount.convert(target=currency, rate=rate)

    def get_unit_discount(self, *, currency: Currency | str | None = None) -> DecimalCurrency:
        if self.quantity == 0:
            msg = "Cannot calculate unit discount for transaction with zero quantity"
            raise ValueError(msg)

        total_discount = self.get_discount(currency=currency)
        return total_discount / self.quantity

    def get_partial_discount(self, quantity: Decimal, *, currency: Currency | str | None = None) -> DecimalCurrency:
        if quantity == self.quantity:
            return self.get_discount(currency=currency)

        unit_discount = self.get_unit_discount(currency=currency)
        return unit_discount * quantity

    # MARK: S104
    # TODO: Move to some sort of S104 mixin/extension
    @property
    def s104_pool_annotation_or_none(self) -> S104PoolAnnotation | None:
        from ..annotation.s104 import S104PoolAnnotation

        return S104PoolAnnotation.get(self.entity)

    @property
    def s104_pool_annotation(self) -> S104PoolAnnotation:
        if (ann := self.s104_pool_annotation_or_none) is None:
            msg = "S104 pool annotation requested but not found. Please ensure you have run a S104 annotator."
            raise ValueError(msg)
        return ann

    def get_s104_holdings_or_none(self) -> S104HoldingsAnnotation | None:
        from ..annotation.s104 import S104HoldingsAnnotation

        return S104HoldingsAnnotation.get(self.entity)

    def get_s104_holdings(self) -> S104HoldingsAnnotation:
        if (ann := self.get_s104_holdings_or_none()) is None:
            msg = "S104 holdings annotation requested but not found. Please ensure you have run a S104 annotator."
            raise ValueError(msg)
        return ann

    def get_previous_s104_holdings_or_none(self) -> S104HoldingsAnnotation | None:
        previous = self.previous
        if previous is None:
            return None
        return previous.get_s104_holdings_or_none()

    def get_previous_s104_holdings(self) -> S104HoldingsAnnotation:
        previous = self.previous
        if previous is None:
            msg = "Previous transaction not found for S104 holdings retrieval."
            raise ValueError(msg)
        return previous.get_s104_holdings()

    @property
    def s104_quantity_matched(self) -> Decimal:
        ann = self.s104_pool_annotation_or_none
        return self.decimal(0) if ann is None else ann.quantity_matched

    @property
    def s104_quantity_unmatched(self) -> Decimal:
        ann = self.s104_pool_annotation_or_none
        return self.quantity if ann is None else ann.quantity_unmatched

    @property
    def s104_fully_matched(self) -> bool:
        ann = self.s104_pool_annotation_or_none
        return ann is not None and ann.fully_matched

    def get_s104_total_proceeds(self) -> DecimalCurrency:
        if not self.type.disposal:
            return self.decimal.currency(0, currency=S104_CURRENCY)

        if not self.type.affects_s104_holdings:
            msg = "Cannot calculate S104 capital gains for a disposal transaction that does not affect S104 holdings."
            raise ValueError(msg)

        total_proceeds = self.decimal.currency(0, currency=S104_CURRENCY)
        remaining = self.quantity

        # Matched portion
        pool = self.s104_pool_annotation_or_none
        if pool is not None:
            total_proceeds += pool.matched_total_proceeds
            remaining = pool.quantity_unmatched
            assert remaining >= 0, "Remaining quantity after matched portion should not be negative."
            assert remaining <= self.quantity, "Remaining quantity after matched portion should not exceed transaction quantity."

        # Unmatched portion
        if remaining > 0:
            total_proceeds += self.get_partial_consideration(remaining, currency=S104_CURRENCY)
            total_proceeds -= self.get_partial_fees(remaining, currency=S104_CURRENCY)

        return total_proceeds

    def get_s104_total_cost(self) -> DecimalCurrency:
        if not self.type.disposal:
            msg = "Cannot calculate S104 total cost for non-disposal transaction."
            raise ValueError(msg)

        if not self.type.affects_s104_holdings:
            msg = "Cannot calculate S104 capital gains for a disposal transaction that does not affect S104 holdings."
            raise ValueError(msg)

        total_cost = self.decimal.currency(0, currency=S104_CURRENCY)
        remaining = self.quantity

        # Matched portion
        pool = self.s104_pool_annotation_or_none
        if pool is not None:
            total_cost += pool.matched_total_cost
            remaining = pool.quantity_unmatched

        # Unmatched portion
        if remaining > 0:
            holdings = self.get_previous_s104_holdings_or_none()
            if holdings is None:
                msg = "Cannot calculate S104 capital gains containing unmatched shares without previous S104 holdings."
                raise ValueError(msg)

            unit_cost_basis = holdings.cost_basis
            total_cost += unit_cost_basis * remaining

        return total_cost

    def get_s104_capital_gain(self) -> DecimalCurrency:
        total_proceeds = self.get_s104_total_proceeds()
        total_cost = self.get_s104_total_cost()
        return total_proceeds - total_cost
