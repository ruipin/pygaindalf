# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import Iterable, Mapping, MutableMapping
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Self, override

from frozendict import frozendict
from iso4217 import Currency
from pydantic import Field, model_validator

from .....util.helpers.empty_class import empty_class
from .....util.helpers.frozendict import FrozenDict
from ...entity import EntityDependencyEventHandlerImpl, EntityDependencyEventType
from ...instrument import InstrumentRecord
from ...transaction import Transaction, TransactionRecord
from ..annotation_impl import AnnotationImpl
from ..annotation_journal import AnnotationJournal
from ..annotation_record import AnnotationRecord
from ..annotation_schema import AnnotationSchema
from ..unique_annotation import UniqueAnnotation


if TYPE_CHECKING:
    from .....util.mixins import ParentType


# MARK: Schema
class ForexAnnotationSchema[
    T_Mapping: Mapping[Currency, Decimal],
](
    AnnotationSchema,
    metaclass=ABCMeta,
):
    if TYPE_CHECKING:
        exchange_rates: T_Mapping = Field(default=...)
        considerations: T_Mapping = Field(default=...)
    else:
        exchange_rates: FrozenDict[Currency, Decimal] = Field(default_factory=frozendict, description="The exchange rates associated with this annotation.")
        considerations: FrozenDict[Currency, Decimal] = Field(
            default_factory=frozendict, description="The considerations in various currencies associated with this annotation."
        )


# MARK: Implementation
class ForexAnnotationImpl(
    AnnotationImpl,
    ForexAnnotationSchema[MutableMapping[Currency, Decimal]] if TYPE_CHECKING else empty_class(),
    metaclass=ABCMeta,
):
    @property
    def transaction(self) -> Transaction:
        parent = self.entity.instance_parent
        if parent is None or not isinstance(parent, Transaction):
            msg = f"{type(self).__name__}.transaction requires parent to be a Transaction, got {type(parent)}"
            raise TypeError(msg)
        return parent

    def get_exchange_rate(self, currency: Currency) -> Decimal | None:
        if currency == self.transaction.currency:
            return self.decimal(1)
        return self.exchange_rates.get(currency)

    def get_consideration(self, currency: Currency) -> Decimal | None:
        if currency == self.transaction.currency:
            return self.transaction.consideration
        return self.considerations.get(currency)

    def get_consideration_in_currency(self, currency: Currency) -> Decimal:
        if (consideration := self.get_consideration(currency)) is not None:
            return consideration
        else:
            assert self.get_exchange_rate(currency) is None, (
                "ForexAnnotation should store both exchange rate and consideration for a currency, but only exchange rate was found."
            )
            return self.transaction.get_consideration_in_currency(currency, use_forex_annotation=False)


# MARK: Journal
class ForexAnnotationJournal(
    ForexAnnotationImpl,
    AnnotationJournal,
    init=False,
):
    def clear(self) -> None:
        self.exchange_rates = {}
        self.considerations = {}

    def _calculate_currency(self, currency: Currency) -> None:
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
        self.considerations[currency] = rate * consideration

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
        return "currency" in attribute or attribute in ("consideration", "date")

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
    AnnotationRecord[ForexAnnotationJournal],
    ForexAnnotationSchema,
    init=False,
    unsafe_hash=True,
):
    @classmethod
    @override
    def __init_dependencies__(cls) -> None:
        super().__init_dependencies__()

        cls.register_dependency_event_handler(ForexAnnotationDependencyHandler())


# MARK: Annotation
class ForexAnnotation(
    ForexAnnotationRecord if TYPE_CHECKING else empty_class(),
    UniqueAnnotation[ForexAnnotationRecord, ForexAnnotationJournal],
    metaclass=ABCMeta,
    init=False,
):
    @classmethod
    @override
    def _do_validate_instance_parent(cls, parent: ParentType) -> None:
        from ...transaction import Transaction

        if not isinstance(parent, Transaction):
            msg = f"ForexAnnotation requires parent to be a Transaction, got {type(parent)}"
            raise TypeError(msg)

    @model_validator(mode="after")
    def _validate_mappings(self) -> Self:
        txn_currency = self.transaction.currency

        if txn_currency in self.exchange_rates or txn_currency in self.considerations:
            msg = f"ForexAnnotation cannot have an entry for the transaction currency {txn_currency}"
            raise ValueError(msg)

        return self


# Register the proxy with the corresponding entity class to ensure isinstance and issubclass checks work correctly.
ForexAnnotationRecord.register_entity_class(ForexAnnotation)
