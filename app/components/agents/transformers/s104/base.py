# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


import datetime
import itertools

from abc import ABCMeta
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, NamedTuple

from pydantic import Field

from .....portfolio.models.annotation.s104 import S104HoldingsAnnotation, S104PoolAnnotation
from .....util.helpers.currency import S104_CURRENCY
from .....util.helpers.decimal_currency import DecimalCurrency
from ..transformer import Transformer, TransformerConfig


if TYPE_CHECKING:
    from decimal import Decimal

    from .....portfolio.models.ledger import Ledger
    from .....portfolio.models.transaction import Transaction


# MARK: Configuration
class S104BaseTransformerConfig(TransformerConfig):
    allow_shorting: bool = Field(default=False, description="Whether to allow shorting of S104 holdings when matching disposals.")

    cost_precision: int | None = Field(
        default=2, description="The number of decimal places for S104 cost calculations. If null, relies on the Decimal context default."
    )


class S104State(NamedTuple):
    shares: Decimal
    cost: DecimalCurrency


class S104BaseTransformer[C: S104BaseTransformerConfig](Transformer[C], metaclass=ABCMeta):
    """Transformer base class that provides logic to handle S104 calculations.

    This base class provides methods to:
    1. Match and annotate transactions using S104 share identification rules.
    2. Calculate and annotate transactions with S104 holdings information.

    More information: https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg51555
    """

    def process_ledger(self, ledger: Ledger, *, match: bool = True, s104_holdings: bool = True) -> None:
        if not ledger.instrument.type.uk_capital_gains_taxed:
            self.log.info(t"Ledger {ledger} instrument type {type} is not subject to UK capital gains tax, skipping S104 processing.")
            return

        # TODO: Handle resume
        self.log.info(t"Processing ledger {ledger} for S104 matching...")

        current_date = None
        current_date_index = 0

        current_s104_holdings = None

        number_matches = 0
        number_s104_holdings = 0

        txns: Sequence[Transaction] = ledger.transactions.sorted

        def _handle_s104_holdings(index: int) -> None:
            nonlocal current_s104_holdings, number_s104_holdings
            if current_date_index != index:
                for _txn in itertools.islice(txns, current_date_index, index):
                    current_s104_holdings = self.annotate_s104_holdings(_txn, current_s104_holdings)
                    number_s104_holdings += 1

        i = 0
        for i, txn in enumerate(txns):
            if current_date != txn.date:
                if s104_holdings:
                    _handle_s104_holdings(i)

                current_date = txn.date
                current_date_index = i
            assert current_date_index >= 0, "Current date index must be non-negative"

            if match:
                others = itertools.islice(txns, current_date_index, None)
                self.match_s104_rule_1_and_2(txn, others, process_s104_holdings=s104_holdings)
                number_matches += 1

        _handle_s104_holdings(i + 1)

        assert not match or number_matches == len(txns), "All transactions must be processed for S104 matching"
        assert not s104_holdings or number_s104_holdings == len(txns), "All transactions must be annotated with S104 holdings"

        self.log.info(t"Completed processing ledger {ledger} for S104 matching")

    # MARK: S104 Matching
    def match_s104_rule_1_and_2(
        self,
        txn: Transaction,
        others: Iterable[Transaction],
        *,
        process_s104_holdings: bool = False,
    ) -> None:
        """Apply S104 matching rules to the given transaction against other transactions.

        The S104 matching rules applied are:
        1. Acquisitions on the same day ("same day rule")
        2. Acquisitions within 30 days ("bed and breakfast rule")

        More information: https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg51555
        """
        # We only process disposal transactions
        if not txn.type.disposal:
            return
        assert txn.quantity > 0, "Disposal transaction must have positive quantity"

        if txn.s104_fully_matched:
            self.log.debug(t"Disposal {txn} already fully matched, skipping")
            return

        timedelta_30d = datetime.timedelta(days=30)
        split_ratio = self.decimal(1)
        for other in others:
            assert other.date >= txn.date, "Other transaction must be on or after disposal transaction date"

            # Stop after 30 days
            if txn.date + timedelta_30d < other.date:
                break

            # Skip self
            if other is txn:
                continue

            # Stock splits
            if other.type.stock_split:
                split_ratio *= other.quantity  # TODO: Dedicated stock split transaction type?
                continue

            # Only match against acquisitions
            if not other.type.acquisition:
                continue

            # Skip fully matched acquisitions
            if other.s104_fully_matched:
                continue

            # Match the transactions
            if split_ratio != 1:
                msg = f"Cannot match disposal {txn} with acquisition {other} after stock split adjustment (split ratio {split_ratio}) is not implemented"
                raise NotImplementedError(msg)
            fully_matched = self.match_disposal_with_acquisition(txn, other)
            if fully_matched:
                self.log.debug(t"Disposal {txn} fully matched after processing acquisition {other}")
                return

        if not process_s104_holdings:
            self.log.warning(t"Disposal {txn} not fully matched after processing all acquisitions within 30 days")

    def match_disposal_with_acquisition(self, disposal: Transaction, acquisition: Transaction) -> bool:
        acq_remaining = acquisition.s104_quantity_unmatched
        assert acq_remaining > 0, "Acquisition must have unmatched shares"

        with self.session(reason=f"Match disposal {disposal} with acquisition {acquisition}"):
            ann = S104PoolAnnotation.get_or_create(disposal)
            dis_remaining = ann.journal.quantity_unmatched

            matched = min(dis_remaining, acq_remaining)
            assert matched >= 0, "Matched shares must be non-negative"

            ann.journal.create_pool(acquisition, quantity=matched)

        self.log.debug(t"Matched {matched} shares between disposal {disposal} and acquisition {acquisition}")
        return ann.fully_matched

    # MARK: S104 Holdings
    def _handle_s104_acquisition(self, txn: Transaction, state: S104State, quantity: Decimal, *, short: bool) -> S104State:
        """Acquisitions: Add any unmatched shares to the S104, increasing cost accordingly.

        If shorting, the quantity and consideration are negative.
        """
        consideration = txn.get_partial_consideration(quantity=quantity, currency=S104_CURRENCY)
        fees = txn.get_partial_fees(quantity=quantity, currency=S104_CURRENCY)
        cost = consideration + fees

        if short:
            quantity = -quantity
            cost = -cost
            assert state.shares <= 0, "Cannot handle short acquisition when shares are positive"
            assert quantity < 0, "Quantity must be negative for short acquisitions"
            assert cost < 0, "Cost must be negative for short acquisitions"
        else:
            assert state.shares >= 0, "Cannot handle long acquisition when shares are negative"
            assert quantity > 0, "Quantity must be positive for long acquisitions"
            assert cost > 0, "Cost must be positive for long acquisitions"

        new_shares = state.shares + quantity
        new_cost = (state.cost + cost).round(self.config.cost_precision)

        return S104State(
            shares=new_shares,
            cost=new_cost,
        )

    def _handle_s104_disposal(self, state: S104State, quantity: Decimal, *, short: bool) -> S104State:
        """Remove any unmatched shares from the S104, decreasing cost accordingly.

        If shorting, the quantity is negative.
        """
        if short:
            quantity = -quantity
            assert state.shares < 0, "Cannot handle short disposal when shares are positive or zero"
            assert quantity < 0, "Quantity must be negative for short disposal"
        else:
            assert state.shares > 0, "Cannot handle long disposal when shares are negative or zero"
            assert quantity > 0, "Quantity must be positive for long disposal"

        cost_impact = -(state.cost * quantity / state.shares)

        if short:
            assert cost_impact > 0, "Cost impact must be positive for short disposal"
        else:
            assert cost_impact < 0, "Cost impact must be negative for long disposal"

        # Reduce cost proportionally
        new_shares = state.shares - quantity
        new_cost = (state.cost + cost_impact).round(self.config.cost_precision)

        # Normalize zero shares
        if new_shares == 0:
            new_shares = self.decimal(0)

        # Ensure cost is zero when shares are zero
        if new_shares == 0 and new_cost != 0:
            new_cost = round(new_cost, ndigits=2)
            if new_cost != 0:
                msg = f"S104 holdings cost should be zero when shares are zero, got {new_cost}"
                raise ValueError(msg)
            new_cost = DecimalCurrency(0, currency=S104_CURRENCY)

        return S104State(
            shares=new_shares,
            cost=new_cost,
        )

    def _handle_acquisition(self, txn: Transaction, state: S104State, unmatched: Decimal) -> tuple[S104State, Decimal]:
        # Short buy-back
        if state.shares < 0:
            if not self.config.allow_shorting:
                msg = "Cannot acquire shares to cover short S104 holdings when shorting is not allowed"
                raise ValueError(msg)
            boughtback = min(-state.shares, unmatched)
            state = self._handle_s104_disposal(state, boughtback, short=True)
            unmatched -= boughtback

        # Long buy
        if unmatched > 0:
            state = self._handle_s104_acquisition(txn, state, quantity=unmatched, short=False)

        return state, unmatched

    def _handle_disposal(self, txn: Transaction, state: S104State, unmatched: Decimal) -> tuple[S104State, Decimal]:
        if unmatched > state.shares and not self.config.allow_shorting:
            msg = f"Cannot dispose of {unmatched} shares from S104 holdings of instrument {txn.instrument.symbol} with only {state.shares} shares. Please ensure all transactions are accounted for or enable shorting."
            raise ValueError(msg)

        # Long sell
        sold = min(state.shares, unmatched)
        if sold > 0:
            state = self._handle_s104_disposal(state, sold, short=False)
            unmatched -= sold

        # Short sell
        if unmatched > 0:
            state = self._handle_s104_acquisition(txn, state, quantity=unmatched, short=True)

        return state, unmatched

    def _handle_stock_split(self, txn: Transaction, state: S104State) -> S104State:
        # Simply multiple the number of shares by the ratio
        ratio = txn.quantity  # TODO: This should maybe be handled by a separate Entity type?

        return S104State(
            shares=state.shares * ratio,
            cost=state.cost,
        )

    def annotate_s104_holdings(self, txn: Transaction, current_s104_holdings: S104HoldingsAnnotation | None) -> S104HoldingsAnnotation:
        """Annotate the given transaction with the updated S104 holdings after it was executed.

        This corresponds to point #3 (and #4 if shorting) of https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg51555

        TODO: Handle stock splits
        """
        self.log.debug(t"Annotating S104 holdings for transaction {txn}...")

        # Copy from current
        state = S104State(
            shares=current_s104_holdings.quantity if current_s104_holdings is not None else self.decimal(0),
            cost=current_s104_holdings.cumulative_cost if current_s104_holdings is not None else self.decimal.currency(0, currency=S104_CURRENCY),
        )

        # If fully matched, no changes
        if txn.type.affects_s104_holdings and not txn.s104_fully_matched:
            unmatched = txn.s104_quantity_unmatched
            assert unmatched > 0, "Transaction must have unmatched shares"

            # Acquisitions
            if txn.type.acquisition:
                state, unmatched = self._handle_acquisition(txn, state, unmatched)

            # Disposals
            elif txn.type.disposal:
                state, unmatched = self._handle_disposal(txn, state, unmatched)

            # Stock splits
            elif txn.type.stock_split:
                state = self._handle_stock_split(txn, state)

            # Unhandled types
            else:
                msg = f"Transaction type {txn.type} affects S104 holdings but is unhandled"
                raise ValueError(msg)

        # Store in a new annotation
        with self.session(reason=f"Annotate S104 holdings for transaction {txn}"):
            ann = S104HoldingsAnnotation.get_or_create(
                txn,
                quantity=state.shares,
                cumulative_cost=state.cost,
            )

        self.log.debug(t"Annotated S104 holdings for transaction {txn}: quantity={ann.quantity}, cost={ann.cumulative_cost}")
        return ann
