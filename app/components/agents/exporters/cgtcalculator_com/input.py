# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


import datetime

from decimal import Decimal
from typing import TYPE_CHECKING, TextIO, override

from pydantic import Field

from .....util.config.models.env_path import EnvForceNewPath
from .....util.helpers.currency import S104_CURRENCY
from ..exporter import DateFilteredExporter, DateFilteredExporterConfig


if TYPE_CHECKING:
    from .....portfolio.models.annotation.s104.s104_holdings_annotation import S104HoldingsAnnotation
    from .....portfolio.models.ledger import Ledger
    from .....portfolio.models.transaction import Transaction


# MARK: Configuration
class CgtCalculatorComExporterConfig(DateFilteredExporterConfig):
    filepath: EnvForceNewPath = Field(description="The file to export the portfolio data to")
    share_factor: Decimal | int = Field(
        default=1,
        description="Factor to convert shares to CGTCalculator.com format, useful when dealing with fractional shares since CGTCalculator does not support them",
    )


# MARK: Exporter
# TODO: Filter by date, which requires an initial "buy" to setup the S104 holdings state >30d before the start date
class CgtCalculatorComExporter(DateFilteredExporter[CgtCalculatorComExporterConfig]):
    @override
    def _do_run(self) -> None:
        with self.config.filepath.open("w", encoding="utf-8") as f:
            f.write("# CGTCalculator.com Input\n")
            f.write("# Portfolio exported by pygaindalf\n\n")

            for ledger in self.context.ledgers:
                self._process_ledger(f, ledger)

    @override
    def _should_include_transaction(self, transaction: Transaction) -> bool:
        if not super()._should_include_transaction(transaction):
            return False

        if not transaction.type.affects_s104_holdings:
            return False
        assert transaction.type.trade or transaction.type.stock_split, f"Transaction must be trade or a stock split, got {transaction.type}."

        return True

    def _get_symbol(self, txn: Transaction) -> str:
        return txn.instrument.symbol.replace(" ", "_")

    def _process_ledger(self, f: TextIO, ledger: Ledger) -> None:
        txns = self._get_transactions(ledger)
        if not txns:
            return
        if not any(txn.type.trade for txn in txns):
            return

        holdings = txns[0].get_previous_s104_holdings_or_none()
        if holdings is not None and holdings.quantity > 0:
            start_date = self.config.start_date or (txns[0].date - datetime.timedelta(days=1))
            self._write_initial(f, holdings, start_date=start_date)

        for transaction in txns:
            self._process_transaction(f, ledger, transaction)

    def _write_initial(self, f: TextIO, holdings: S104HoldingsAnnotation, *, start_date: datetime.date | None = None) -> None:
        txn = holdings.transaction

        # 1. Transaction Type
        f.write("B ")

        # 2. Date
        if start_date is None:
            start_date = txn.date
        f.write(start_date.strftime("%Y-%m-%d"))
        f.write(" ")

        # 3. Symbol
        f.write(self._get_symbol(txn))
        f.write(" ")

        # 4. Shares
        quantity = holdings.quantity * self.config.share_factor
        f.write(f"{quantity:.0f}")
        f.write(" ")

        # 5. Unit Price
        unit_price = holdings.cumulative_cost
        f.write(f"{unit_price:.2f}")
        f.write(" ")

        # 6. Fees / Stamp Duty
        f.write("0 0 ")

        # Done
        f.write("\n")

    def _process_transaction(self, f: TextIO, _ledger: Ledger, transaction: Transaction) -> None:
        if not transaction.type.affects_s104_holdings:
            return

        if transaction.type.trade:
            self._write_trade(f, transaction)
        elif transaction.type.stock_split:
            self._write_stock_split(f, transaction)
        else:
            msg = f"Unhandled transaction type {transaction.type} in CGTCalculator.com exporter."
            raise NotImplementedError(msg)

    def _write_trade(self, f: TextIO, transaction: Transaction) -> None:
        # 1. Transaction Type
        f.write("B" if transaction.type.acquisition else "S")
        f.write(" ")

        # 2. Date
        f.write(transaction.date.strftime("%Y-%m-%d"))
        f.write(" ")

        # 3. Symbol
        f.write(self._get_symbol(transaction))
        f.write(" ")

        # 4. Shares
        quantity = transaction.quantity * self.config.share_factor
        f.write(f"{quantity:.0f}")
        f.write(" ")

        # 5. Unit Price
        unit_price = transaction.get_unit_consideration(currency=S104_CURRENCY)
        f.write(f"{unit_price:.2f}")
        f.write(" ")

        # 6. Fees
        fees = transaction.get_fees(currency=S104_CURRENCY)
        f.write(f"{fees:.2f}")
        f.write(" ")

        # 7. Stamp Duty
        # TODO: Calculate stamp duty properly?
        f.write("0 ")

        # Done
        f.write("\n")

    def _write_stock_split(self, f: TextIO, transaction: Transaction) -> None:
        # 1. Transaction Type
        f.write("R ")

        # 2. Date
        f.write(transaction.date.strftime("%Y-%m-%d"))
        f.write(" ")

        # 3. Symbol
        f.write(self._get_symbol(transaction))
        f.write(" ")

        # 4. Split Ratio
        f.write(f"{transaction.quantity:.2f}")

        # Done
        f.write("\n")


COMPONENT = CgtCalculatorComExporter
