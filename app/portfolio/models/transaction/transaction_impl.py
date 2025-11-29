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
    def get_consideration(self, currency: Currency | str, *, use_forex_annotation: bool = True) -> DecimalCurrency:
        currency = Currency(currency)

        if currency == self.currency:
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

        return self.get_partial_consideration(self.quantity, currency=currency)

    @property
    def unit_consideration(self) -> DecimalCurrency:
        return self.get_unit_consideration()

    def get_fees(self, currency: Currency | str | None) -> DecimalCurrency:
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

    # MARK: S104
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
