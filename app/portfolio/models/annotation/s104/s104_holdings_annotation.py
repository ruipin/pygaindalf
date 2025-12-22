# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from decimal import Decimal
from typing import TYPE_CHECKING, Self, override

from pydantic import Field, model_validator

from .....util.helpers.decimal_currency import DecimalCurrency
from .....util.helpers.empty_class import empty_class
from ..annotation_schema import AnnotationSchema
from ..transaction_annotation import TransactionAnnotationImpl, TransactionAnnotationJournal, TransactionAnnotationRecord, UniqueTransactionAnnotation
from .s104_dependency_handler import S104AnnotationDependencyHandler


# MARK: Schema
class S104HoldingsAnnotationSchema(
    AnnotationSchema,
    metaclass=ABCMeta,
):
    quantity: Decimal = Field(description="The total shares in the S104 pool after the associated transaction.")
    cumulative_cost: DecimalCurrency = Field(description="The cumulative cost associated with the shares in the S104 pool.")


# MARK: Implementation
class S104HoldingsAnnotationImpl(
    TransactionAnnotationImpl,
    S104HoldingsAnnotationSchema if TYPE_CHECKING else empty_class(),
    metaclass=ABCMeta,
):
    @property
    def cost_basis(self) -> DecimalCurrency:
        return self.cumulative_cost / self.quantity

    @property
    def is_short(self) -> bool:
        return self.quantity < 0

    @property
    def is_long(self) -> bool:
        return self.quantity > 0

    @property
    def is_zero(self) -> bool:
        return self.quantity == 0

    @property
    @override
    def previous(self) -> S104HoldingsAnnotation | None:
        return self.transaction.get_previous_s104_holdings_or_none()

    @property
    def previous_quantity(self) -> Decimal:
        if (previous := self.previous) is None:
            return Decimal(0)
        return previous.quantity

    @property
    def previous_cumulative_cost(self) -> DecimalCurrency:
        if (previous := self.previous) is None:
            return DecimalCurrency(0)
        return previous.cumulative_cost

    @property
    def previous_cost_basis(self) -> DecimalCurrency:
        if (previous := self.previous) is None:
            return DecimalCurrency(0)
        return previous.cost_basis


# MARK: Journal
class S104HoldingsAnnotationJournal(
    S104HoldingsAnnotationImpl,
    TransactionAnnotationJournal,
    init=False,
):
    pass


# MARK: Record
class S104HoldingsAnnotationRecord(
    S104HoldingsAnnotationImpl,
    TransactionAnnotationRecord[S104HoldingsAnnotationJournal],
    S104HoldingsAnnotationSchema,
    init=False,
    unsafe_hash=True,
):
    @classmethod
    @override
    def __init_dependencies__(cls) -> None:
        super().__init_dependencies__()

        cls.register_dependency_event_handler(S104AnnotationDependencyHandler())

    @model_validator(mode="after")
    def _validate_state(self) -> Self:
        if self.quantity == 0 and self.cumulative_cost != 0:
            msg = f"S104 holdings annotation cannot have zero quantity with non-zero cumulative cost, got {self.cumulative_cost}."
            raise ValueError(msg)

        if self.quantity < 0 and self.cumulative_cost >= 0:
            msg = f"S104 holdings annotation with negative quantity must have negative cumulative cost, got {self.cumulative_cost}."
            raise ValueError(msg)

        if self.quantity > 0 and self.cumulative_cost <= 0:
            msg = f"S104 holdings annotation with positive quantity must have positive cumulative cost, got {self.cumulative_cost}."
            raise ValueError(msg)

        return self


# MARK: Annotation
class S104HoldingsAnnotation(
    S104HoldingsAnnotationRecord if TYPE_CHECKING else empty_class(),
    UniqueTransactionAnnotation[S104HoldingsAnnotationRecord, S104HoldingsAnnotationJournal],
    metaclass=ABCMeta,
    init=False,
):
    pass


# Register the proxy with the corresponding entity class to ensure isinstance and issubclass checks work correctly.
S104HoldingsAnnotationRecord.register_entity_class(S104HoldingsAnnotation)
