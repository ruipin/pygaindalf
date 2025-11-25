# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import MutableSequence, Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, override

from iso4217 import Currency
from pydantic import Field, field_validator

from app.util.models import SingleInitializationModel

from .....util.helpers.empty_class import empty_class
from .....util.models import NonChild
from ...transaction import Transaction
from ..annotation_schema import AnnotationSchema
from ..transaction_annotation import TransactionAnnotationImpl, TransactionAnnotationJournal, TransactionAnnotationRecord, UniqueTransactionAnnotation
from .s104_dependency_handler import S104AnnotationDependencyHandler


if TYPE_CHECKING:
    from .....util.helpers.decimal_currency import DecimalCurrency


S104_CURRENCY = Currency("GBP")


# MARK: S104 Pool
class S104Pool(SingleInitializationModel):
    acquisition: NonChild[Transaction] = Field(description="The acquisition transaction for this S104 pool.")
    disposal: NonChild[Transaction] = Field(description="The disposal transaction for this S104 pool.")
    quantity: Decimal = Field(description="The quantity of shares in this S104 pool.")

    @field_validator("acquisition", mode="after")
    def _validate_acquisition(cls, acquisition: Transaction) -> Transaction:
        if not acquisition.type.acquisition:
            msg = f"S104PoolInfo acquisition transaction must be of acquisition type, got {acquisition.type}"
            raise ValueError(msg)
        return acquisition

    @field_validator("disposal", mode="after")
    def _validate_disposal(cls, disposal: Transaction) -> Transaction:
        if not disposal.type.disposal:
            msg = f"S104PoolInfo disposal transaction must be of disposal type, got {disposal.type}"
            raise ValueError(msg)
        return disposal

    @field_validator("quantity", mode="after")
    def _validate_quantity(cls, quantity: Decimal) -> Decimal:
        if quantity <= Decimal(0):
            msg = f"S104PoolInfo quantity must be positive, got {quantity}"
            raise ValueError(msg)
        return quantity

    @property
    def unit_cost(self) -> DecimalCurrency:
        return self.acquisition.get_partial_consideration(Decimal(1), currency=S104_CURRENCY)

    @property
    def total_cost(self) -> DecimalCurrency:
        return self.acquisition.get_partial_consideration(self.quantity, currency=S104_CURRENCY)

    @property
    def unit_proceeds(self) -> DecimalCurrency:
        return self.disposal.get_partial_consideration(Decimal(1), currency=S104_CURRENCY)

    @property
    def total_proceeds(self) -> DecimalCurrency:
        return self.disposal.get_partial_consideration(self.quantity, currency=S104_CURRENCY)

    @property
    def total_gain(self) -> DecimalCurrency:
        return self.total_proceeds - self.total_cost

    @property
    def unit_gain(self) -> DecimalCurrency:
        return self.total_gain / self.quantity


# MARK: Schema
class S104PoolAnnotationSchema[
    T_Sequence: Sequence[S104Pool],
](
    AnnotationSchema,
    metaclass=ABCMeta,
):
    if TYPE_CHECKING:
        pools: T_Sequence = Field(default=...)
    else:
        pools: tuple[S104Pool, ...] = Field(default_factory=tuple, description="The pools associated with this annotation.")


# MARK: Implementation
class S104PoolAnnotationImpl[
    T_Sequence: Sequence[S104Pool],
](
    TransactionAnnotationImpl,
    S104PoolAnnotationSchema[T_Sequence] if TYPE_CHECKING else empty_class(),
    metaclass=ABCMeta,
):
    @property
    def quantity_matched(self) -> Decimal:
        result = self.decimal(0)
        for pool in self.pools:
            result += pool.quantity
        assert result >= 0, "Matched quantity cannot be negative"
        assert result <= self.transaction.quantity, "Matched quantity cannot exceed transaction quantity"
        return result

    @property
    def quantity_unmatched(self) -> Decimal:
        quantity = self.transaction.quantity
        result = quantity - self.quantity_matched
        assert result >= 0, "Unmatched quantity cannot be negative"
        assert result <= quantity, "Unmatched quantity cannot exceed transaction quantity"
        return result

    @property
    def fully_matched(self) -> bool:
        return self.quantity_unmatched <= 0

    @property
    def unmatched_cost_basis(self) -> DecimalCurrency:
        if self.transaction.type.acquisition:
            return self.transaction.get_partial_consideration(Decimal(1), currency=S104_CURRENCY)

        else:
            s104_holdings = self.transaction.get_previous_s104_holdings_or_none()
            if s104_holdings is None:
                msg = "Cannot calculate unmatched cost without previous S104 holdings for disposal transaction."
                raise ValueError(msg)

            return s104_holdings.cost_basis if s104_holdings is not None else self.decimal.currency(0, currency=S104_CURRENCY)

    @property
    def unmatched_total_cost(self) -> DecimalCurrency:
        return self.unmatched_cost_basis * self.quantity_unmatched

    @property
    def matched_total_cost(self) -> DecimalCurrency:
        return sum((pool.total_cost for pool in self.pools), start=self.decimal.currency(0, currency=S104_CURRENCY))

    @property
    def matched_cost_basis(self) -> DecimalCurrency:
        return self.matched_total_cost / self.quantity_matched

    @property
    def total_cost(self) -> DecimalCurrency:
        return self.matched_total_cost + self.unmatched_total_cost

    @property
    def cost_basis(self) -> DecimalCurrency:
        return self.total_cost / self.transaction.quantity


# MARK: Journal
class S104PoolAnnotationJournal(
    S104PoolAnnotationImpl[MutableSequence[S104Pool]],
    TransactionAnnotationJournal,
    init=False,
):
    def _append_pool(self, pool: S104Pool) -> None:
        txn = self.transaction
        if txn is not pool.acquisition and txn is not pool.disposal:
            msg = f"Pool acquisition or disposal must match the annotation transaction, got {pool.acquisition} and {pool.disposal}"
            raise ValueError(msg)

        if pool.quantity > self.quantity_unmatched:
            msg = f"Cannot append pool with quantity {pool.quantity} greater than unmatched quantity {self.quantity_unmatched}"
            raise ValueError(msg)

        other = pool.disposal if txn is pool.acquisition else pool.acquisition
        if txn.instrument is not other.instrument:
            msg = f"Transactions must have the same instrument, got {txn.instrument} and {other.instrument}"
            raise ValueError(msg)

        self.pools.append(pool)

    def create_pool(self, other: Transaction, *, quantity: Decimal) -> None:
        txn = self.transaction

        if txn.instrument is not other.instrument:
            msg = f"Transactions must have the same instrument, got {txn.instrument} and {other.instrument}"
            raise ValueError(msg)

        if not (txn.type.acquisition or txn.type.disposal):
            msg = f"Transaction {txn} must be acquisition or disposal to create S104 pool."
            raise ValueError(msg)
        if not (other.type.acquisition or other.type.disposal):
            msg = f"Transaction {other} must be acquisition or disposal to create S104 pool."
            raise ValueError(msg)
        if txn.type == other.type:
            msg = f"Transactions {txn} and {other} must be of opposite types to create S104 pool."
            raise ValueError(msg)

        acquisition = txn if txn.type.acquisition else other
        disposal = txn if txn.type.disposal else other
        pool_info = S104Pool(
            acquisition=acquisition,
            disposal=disposal,
            quantity=quantity,
        )

        self._append_pool(pool_info)
        S104PoolAnnotation.get_or_create(other).journal._append_pool(pool_info)  # noqa: SLF001 as this is the same class


# MARK: Record
class S104PoolAnnotationRecord(
    S104PoolAnnotationImpl,
    TransactionAnnotationRecord[S104PoolAnnotationJournal],
    S104PoolAnnotationSchema,
    init=False,
    unsafe_hash=True,
):
    @classmethod
    @override
    def __init_dependencies__(cls) -> None:
        super().__init_dependencies__()

        cls.register_dependency_event_handler(S104AnnotationDependencyHandler())


# MARK: Annotation
class S104PoolAnnotation(
    S104PoolAnnotationRecord if TYPE_CHECKING else empty_class(),
    UniqueTransactionAnnotation[S104PoolAnnotationRecord, S104PoolAnnotationJournal],
    metaclass=ABCMeta,
    init=False,
):
    pass


# Register the proxy with the corresponding entity class to ensure isinstance and issubclass checks work correctly.
S104PoolAnnotationRecord.register_entity_class(S104PoolAnnotation)
