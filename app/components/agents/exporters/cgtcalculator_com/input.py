# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import TYPE_CHECKING, TextIO, override

from iso4217 import Currency
from pydantic import Field

from .....util.config.models.env_path import EnvForceNewPath
from ..exporter import Exporter, ExporterConfig


if TYPE_CHECKING:
    from .....portfolio.models.ledger import Ledger
    from .....portfolio.models.transaction import Transaction


S104_CURRENCY = Currency("GBP")


# MARK: Configuration
class CgtCalculatorComExporterConfig(ExporterConfig):
    filepath: EnvForceNewPath = Field(description="The file to export the portfolio data to")


# MARK: Exporter
class CgtCalculatorComExporter(Exporter[CgtCalculatorComExporterConfig]):
    @override
    def _do_run(self) -> None:
        with self.config.filepath.open("w", encoding="utf-8") as f:
            f.write("# CGTCalculator.com Input\n")
            f.write("# Portfolio exported by pygaindalf\n\n")

            for ledger in self.context.ledgers:
                self._process_ledger(f, ledger)

    def _process_ledger(self, f: TextIO, ledger: Ledger) -> None:
        for transaction in ledger:
            self._process_transaction(f, ledger, transaction)

    def _process_transaction(self, f: TextIO, ledger: Ledger, transaction: Transaction) -> None:
        if not transaction.type.affects_s104_holdings:
            return
        assert transaction.type.acquisition or transaction.type.disposal, f"Transaction must be acquisition or disposal, got {transaction.type}."

        # 1. Transaction Type
        f.write("B" if transaction.type.acquisition else "S")
        f.write(" ")

        # 2. Date
        f.write(transaction.date.strftime("%Y-%m-%d"))
        f.write(" ")

        # 3. Symbol
        symbol = ledger.instrument.ticker or ledger.instrument.isin
        assert symbol is not None, "Ledger must have an instrument with either ticker or ISIN."
        f.write(symbol)
        f.write(" ")

        # 4. Shares
        f.write(f"{transaction.quantity:.2f}")
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


COMPONENT = CgtCalculatorComExporter
