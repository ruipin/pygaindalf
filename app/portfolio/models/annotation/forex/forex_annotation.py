# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import Iterable, Mapping, MutableMapping
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Self, override

from frozendict import frozendict
from iso4217 import Currency
from pydantic import Field, field_validator, model_validator

from .....util.helpers.decimal_currency import DecimalCurrency
from .....util.helpers.empty_class import empty_class
from .....util.helpers.frozendict import FrozenDict
from ...entity import EntityDependencyEventHandlerImpl, EntityDependencyEventType
from ...instrument import InstrumentRecord
from ...transaction import TransactionRecord
from ..annotation_schema import AnnotationSchema
from ..transaction_annotation import TransactionAnnotationImpl, TransactionAnnotationJournal, TransactionAnnotationRecord, UniqueTransactionAnnotation


# MARK: Schema
class ForexAnnotationSchema[
    T_Decimal_Mapping: Mapping[Currency, Decimal],
    T_Currency_Mapping: Mapping[Currency, DecimalCurrency],
](
    AnnotationSchema,
    metaclass=ABCMeta,
):
    if TYPE_CHECKING:
        exchange_rates: T_Decimal_Mapping = Field(default=...)
        considerations: T_Currency_Mapping = Field(default=...)
    else:
        exchange_rates: FrozenDict[Currency, Decimal] = Field(default_factory=frozendict, description="The exchange rates associated with this annotation.")
        considerations: FrozenDict[Currency, DecimalCurrency] = Field(
            default_factory=frozendict, description="The considerations in various currencies associated with this annotation."
        )


# MARK: Implementation
class ForexAnnotationImpl[
    T_Decimal_Mapping: Mapping[Currency, Decimal],
    T_Currency_Mapping: Mapping[Currency, DecimalCurrency],
](
    TransactionAnnotationImpl,
    ForexAnnotationSchema[T_Decimal_Mapping, T_Currency_Mapping] if TYPE_CHECKING else empty_class(),
    metaclass=ABCMeta,
):
    def get_exchange_rate(self, currency: Currency) -> Decimal:
        if currency == self.transaction.currency:
            return self.decimal(1)
        if (result := self.exchange_rates.get(currency)) is not None:
            return result
        return self.transaction.get_exchange_rate(currency, use_forex_annotation=False)

    def get_consideration(self, currency: Currency) -> DecimalCurrency:
        if currency == self.transaction.currency:
            return self.transaction.consideration
        elif (result := self.considerations.get(currency)) is not None:
            return result
        else:
            return self.transaction.get_consideration_in_currency(currency, use_forex_annotation=False)


# MARK: Journal
class ForexAnnotationJournal(
    ForexAnnotationImpl[
        MutableMapping[Currency, Decimal],
        MutableMapping[Currency, DecimalCurrency],
    ],
    TransactionAnnotationJournal,
    init=False,
):
    def clear(self) -> None:
        self.exchange_rates = {}
        self.considerations = {}

    def _calculate_currency(self, currency: Currency) -> None:
        assert isinstance(currency, Currency), f"Expected Currency instance, got {type(currency).__name__}."

        transaction = self.transaction

        # fmt: off
        source        = transaction.get_journal_field("currency"     , create=False)
        date          = transaction.get_journal_field("date"         , create=False)
        consideration = transaction.get_journal_field("consideration", create=False)
        # fmt: on

        rate = self.exchange_rates[currency] = self.forex_provider.get_daily_rate(
            source=source,
            target=currency,
            date=date,
        )
        self.considerations[currency] = DecimalCurrency(rate * consideration, currency=currency)

    def recalculate(self) -> None:
        currencies = self.exchange_rates.keys()

        self.clear()

        for currency in currencies:
            self._calculate_currency(currency)

    def add_currency(self, currency: Currency | Iterable[Currency]) -> None:
        if isinstance(currency, Iterable):
            for cur in currency:
                self.add_currency(cur)
            return

        assert isinstance(currency, Currency), f"Expected Currency instance, got {type(currency).__name__}."

        if currency is self.transaction.get_journal_field("currency", create=False):
            return

        if currency not in self.exchange_rates:
            self._calculate_currency(currency)


# MARK: Dependency handler
class ForexAnnotationDependencyHandler(
    EntityDependencyEventHandlerImpl["ForexAnnotationRecord", TransactionRecord | InstrumentRecord],
    init=False,
):
    on_updated = True
    on_deleted = False

    @staticmethod
    @override
    def entity_matchers(owner: ForexAnnotationRecord, record: TransactionRecord | InstrumentRecord) -> bool:
        return record is owner.record_parent or record is owner.transaction.instrument

    @staticmethod
    @override
    def attribute_matchers(owner: ForexAnnotationRecord, record: TransactionRecord | InstrumentRecord, attribute: str, value: Any) -> bool:
        return attribute in ("consideration", "date")

    @staticmethod
    @override
    def handler(
        owner: ForexAnnotationRecord,
        event: EntityDependencyEventType,
        record: TransactionRecord | InstrumentRecord,
        *,
        matched_attributes: frozenset[str] | None = None,
    ) -> None:
        owner.journal.recalculate()


# MARK: Record
class ForexAnnotationRecord(
    ForexAnnotationImpl,
    TransactionAnnotationRecord[ForexAnnotationJournal],
    ForexAnnotationSchema,
    init=False,
    unsafe_hash=True,
):
    @classmethod
    @override
    def __init_dependencies__(cls) -> None:
        super().__init_dependencies__()

        cls.register_dependency_event_handler(ForexAnnotationDependencyHandler())

    @field_validator("considerations", mode="before")
    def validate_considerations(cls, value: Any) -> FrozenDict[Currency, DecimalCurrency]:
        if not isinstance(value, Mapping):
            msg = f"ForexAnnotation considerations must be a mapping, got {type(value).__name__}."
            raise TypeError(msg)

        validated: dict[Currency, DecimalCurrency] = {}
        for currency, consideration in value.items():
            if not isinstance(currency, Currency):
                currency = Currency(currency)

            if not isinstance(consideration, (Decimal, DecimalCurrency)):
                consideration = DecimalCurrency(consideration, currency=currency)

            if isinstance(consideration, Decimal) or consideration.currency:
                validated[currency] = DecimalCurrency(consideration, currency=currency)
            else:
                if consideration.currency is not currency:
                    msg = f"ForexAnnotation considerations currency must match the mapping key, got {consideration.currency} and {currency}."
                    raise ValueError(msg)
                validated[currency] = consideration

        return frozendict(validated)

    @model_validator(mode="after")
    def _validate_mappings(self) -> Self:
        txn_currency = self.transaction.currency

        if txn_currency in self.exchange_rates or txn_currency in self.considerations:
            msg = f"ForexAnnotation cannot have an entry for the transaction currency {txn_currency}"
            raise ValueError(msg)

        return self


# MARK: Annotation
class ForexAnnotation(
    ForexAnnotationRecord if TYPE_CHECKING else empty_class(),
    UniqueTransactionAnnotation[ForexAnnotationRecord, ForexAnnotationJournal],
    metaclass=ABCMeta,
    init=False,
):
    pass


# Register the proxy with the corresponding entity class to ensure isinstance and issubclass checks work correctly.
ForexAnnotationRecord.register_entity_class(ForexAnnotation)
