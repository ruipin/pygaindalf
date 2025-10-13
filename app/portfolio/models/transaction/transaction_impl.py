# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from typing import TYPE_CHECKING

from iso4217 import Currency
from pydantic import computed_field

from ....util.helpers.empty_class import empty_class
from ..entity import EntityImpl
from ..instrument import Instrument
from .transaction_schema import TransactionSchema


if TYPE_CHECKING:
    from decimal import Decimal


class TransactionImpl(
    EntityImpl,
    TransactionSchema if TYPE_CHECKING else empty_class(),
    metaclass=ABCMeta,
):
    # MARK: Instrument
    @computed_field(description="The financial instrument associated with this transaction, derived from its parent ledger.")
    @property
    def instrument(self) -> Instrument:
        from ..ledger import Ledger

        parent = self.entity.instance_parent
        if parent is None or not isinstance(parent, Ledger):
            msg = f"Transaction.instrument requires parent to be a Ledger, got {type(parent)}"
            raise TypeError(msg)
        return parent.instrument

    # MARK: Currency
    @computed_field(description="The currency in which the transaction is denominated. If not provided, it defaults to the instrument's currency.")
    @property
    def currency(self) -> Currency:
        if (currency := self.txn_currency) is not None:
            return currency
        elif self.is_journal:
            return self.instrument.get_journal_field("currency", create=False)
        else:
            return self.instrument.currency

    # MARK: Forex
    def get_consideration_in_currency(self, currency: Currency, *, use_forex_annotation: bool = True) -> Decimal:
        if use_forex_annotation:
            from ..annotation.forex import ForexAnnotation

            if (annotation := self.get_annotation(ForexAnnotation)) is not None:
                return annotation.get_consideration_in_currency(currency)

        return self.forex_provider.convert_currency(amount=self.consideration, source=self.currency, target=currency, date=self.date)
