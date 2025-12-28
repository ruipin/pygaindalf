# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


import dataclasses
import datetime

from collections.abc import Callable, Mapping, MutableMapping, Sequence
from csv import DictWriter
from typing import TYPE_CHECKING, ClassVar, TextIO, override

from iso4217 import Currency
from pydantic import Field

from app.portfolio.models.transaction import Transaction

from ....util.config.models.env_path import EnvForceNewPath
from ....util.helpers.decimal_currency import DecimalCurrency
from .exporter import DateFilteredExporter, DateFilteredExporterConfig


if TYPE_CHECKING:
    from decimal import Decimal

    from ....portfolio.models.annotation.s104.s104_holdings_annotation import S104HoldingsAnnotation
    from ....portfolio.models.annotation.s104.s104_pool_annotation import S104Pool
    from ....portfolio.models.ledger import Ledger
    from ....portfolio.models.transaction import Transaction

S104_CURRENCY = Currency("GBP")

type CsvCell = str | int | Decimal
type MutableCsvRow = MutableMapping[str, CsvCell]


# MARK: Configuration
class CgtReportExporterConfig(DateFilteredExporterConfig):
    filepath: EnvForceNewPath = Field(description="The file to export the portfolio data to")

    cost_precision: int = Field(default=2, description="The number of decimal places for S104 costs.")


# Utility class
@dataclasses.dataclass
class S104Summary:
    buys: int = 0
    sells: int = 0

    gain: DecimalCurrency = dataclasses.field(default_factory=lambda: DecimalCurrency(0))

    start_date: datetime.date | None = None
    end_date: datetime.date | None = None

    @property
    def trades(self) -> int:
        return self.buys + self.sells

    def _min_first_date(self, other: datetime.date | None) -> None:
        if other is None:
            return
        self.start_date = min(self.start_date, other) if self.start_date is not None else other

    def _max_last_date(self, other: datetime.date | None) -> None:
        if other is None:
            return
        self.end_date = max(self.end_date, other) if self.end_date is not None else other

    def add_date(self, date: datetime.date) -> None:
        self._min_first_date(date)
        self._max_last_date(date)

    def add_transaction(self, transaction: Transaction, cost_precision: int) -> None:
        if transaction.type.acquisition:
            self.buys += 1
        elif transaction.type.disposal:
            self.sells += 1
            self.gain += round(transaction.get_s104_capital_gain(), cost_precision)
        else:
            msg = f"Transaction must be acquisition or disposal, got {transaction.type}."
            raise ValueError(msg)

        self.add_date(transaction.date)

    def add_summary(self, other: S104Summary) -> None:
        self.buys += other.buys
        self.sells += other.sells
        self.gain += other.gain
        self._min_first_date(other.start_date)
        self._max_last_date(other.end_date)


# MARK: Exporter
class CgtReportExporter(DateFilteredExporter[CgtReportExporterConfig]):
    MAPPINGS_BUY_SELL: ClassVar[Mapping[str, Callable[[CgtReportExporter, Transaction], CsvCell]]] = {
        "ID": lambda _self, txn: f"#{txn.uid.id}",
        "Type": lambda _self, txn: txn.type.name,
        "Date": lambda _self, txn: txn.date.strftime("%Y-%m-%d"),
        "Quantity": lambda _self, txn: txn.quantity,
        "Fees": lambda self, txn: round(txn.get_fees(currency=S104_CURRENCY), self.config.cost_precision),
        "S104 Holdings": lambda _self, txn: txn.get_s104_holdings().quantity,
        "S104 Cumulative Cost": lambda self, txn: round(txn.get_s104_holdings().cumulative_cost, self.config.cost_precision),
    }

    MAPPINGS_BUY: ClassVar[Mapping[str, Callable[[CgtReportExporter, Transaction], CsvCell]]] = {
        "FMV": lambda self, txn: round(txn.get_consideration(currency=S104_CURRENCY), self.config.cost_precision),
    }

    MAPPINGS_SELL: ClassVar[Mapping[str, Callable[[CgtReportExporter, Transaction], CsvCell]]] = {
        "S104 Total Cost": lambda self, txn: round(txn.get_s104_total_cost(), self.config.cost_precision),
        "Disposal Proceeds": lambda self, txn: round(txn.get_s104_total_proceeds(), self.config.cost_precision),
        "Gain": lambda self, txn: round(txn.get_s104_capital_gain(), self.config.cost_precision),
    }

    MAPPINGS_MATCH: ClassVar[Mapping[str, Callable[[CgtReportExporter, Transaction, S104Pool], CsvCell]]] = {
        "Match ID": lambda _self, main, pool: f"#{pool.acquisition.uid.id}" if main is pool.disposal else f"#{pool.disposal.uid.id}",
        "Match Date": lambda _self, main, pool: pool.acquisition.date.strftime("%Y-%m-%d")
        if main is pool.disposal
        else pool.disposal.date.strftime("%Y-%m-%d"),
        "Match Quantity": lambda _self, _main, pool: pool.quantity,
        "Match Cost": lambda self, _main, pool: round(pool.total_cost, self.config.cost_precision),
        "Match Proceeds": lambda self, _main, pool: round(pool.total_proceeds, self.config.cost_precision),
    }

    MAPPINGS_HOLDINGS: ClassVar[Mapping[str, Callable[[CgtReportExporter, S104HoldingsAnnotation | None], CsvCell]]] = {
        "S104 Holdings": lambda _self, holdings: holdings.quantity if holdings else 0,
        "S104 Cumulative Cost": lambda self, holdings: round(holdings.cumulative_cost, self.config.cost_precision)
        if holdings
        else DecimalCurrency(0, currency=S104_CURRENCY),
    }

    HEADERS: ClassVar[Sequence[str]] = (
        "Symbol",
        "ID",
        "Type",
        "Date",
        "Quantity",
        "FMV",
        "Fees",
        "S104 Total Cost",
        "Disposal Proceeds",
        "Gain",
        "Match ID",
        "Match Date",
        "Match Quantity",
        "Match Cost",
        "Match Proceeds",
        "S104 Holdings",
        "S104 Cumulative Cost",
    )

    @override
    def _do_run(self) -> None:
        with self.config.filepath.open("w", encoding="utf-8") as f:
            summary = S104Summary(start_date=self.config.start_date, end_date=self.config.end_date)

            for ledger in self.context.ledgers:
                ledger_summary = self._process_ledger(f, ledger)
                if ledger_summary is not None:
                    summary.add_summary(ledger_summary)

            self._write_summary(f, summary)

    def _process_ledger(self, f: TextIO, ledger: Ledger) -> S104Summary | None:
        txns = self._get_transactions(ledger)
        if not txns:
            return None

        w = DictWriter(f, fieldnames=self.HEADERS, extrasaction="raise")

        start_date = self.config.start_date or (txns[0].date - datetime.timedelta(days=1))
        summary = S104Summary(start_date=start_date, end_date=self.config.end_date)
        self._write_header(f, w, ledger, txns, summary)

        for transaction in txns:
            self._process_transaction(w, ledger, transaction, summary)

        self._write_footer(f, ledger, txns, summary)

        return summary

    def _write_header(self, f: TextIO, w: DictWriter, ledger: Ledger, txns: Sequence[Transaction], summary: S104Summary) -> None:
        assert txns, "Transactions should not be empty when writing header."

        f.write("\n\n")

        w.writeheader()
        self._write_holdings(w, ledger, txns[0].get_previous_s104_holdings_or_none(), date=summary.start_date)

    def _write_holdings(self, w: DictWriter, ledger: Ledger, holdings: S104HoldingsAnnotation | None, *, date: datetime.date | None = None) -> None:
        date = date if date else holdings.transaction.date if holdings else None
        if date is None:
            msg = "Date must be provided if holdings is None."
            raise ValueError(msg)

        row: MutableCsvRow = {
            "Type": "INITIAL",
            "Symbol": ledger.symbol,
            "Date": date.strftime("%Y-%m-%d"),
        }

        for header in self.HEADERS:
            fn = self.MAPPINGS_HOLDINGS.get(header)
            if fn is None:
                if header not in row:
                    row[header] = ""
                continue

            row[header] = fn(self, holdings)

        w.writerow(row)

    @override
    def _should_include_transaction(self, transaction: Transaction) -> bool:
        if not super()._should_include_transaction(transaction):
            return False

        if not transaction.type.affects_s104_holdings:
            return False
        assert transaction.type.acquisition or transaction.type.disposal, f"Transaction must be acquisition or disposal, got {transaction.type}."

        return True

    def _process_transaction(self, w: DictWriter, ledger: Ledger, transaction: Transaction, summary: S104Summary) -> None:
        if not self._should_include_transaction(transaction):
            return

        summary.add_transaction(transaction, self.config.cost_precision)

        # Sell Transaction
        self._write_buy_sell(w, ledger, transaction)

        # Matches
        self._write_matches(w, ledger, transaction)

    def _write_buy_sell(self, w: DictWriter, ledger: Ledger, transaction: Transaction) -> None:
        row: MutableCsvRow = {
            "Symbol": ledger.symbol,
        }

        for header in self.HEADERS:
            fn = self.MAPPINGS_BUY_SELL.get(header)
            if fn is None:
                if transaction.type.disposal:
                    fn = self.MAPPINGS_SELL.get(header)
                elif transaction.type.acquisition:
                    fn = self.MAPPINGS_BUY.get(header)
            if fn is None:
                if header not in row:
                    row[header] = ""
                continue

            row[header] = fn(self, transaction)

        w.writerow(row)

    def _write_matches(self, w: DictWriter, ledger: Ledger, transaction: Transaction) -> None:
        ann = transaction.s104_pool_annotation_or_none
        if ann is None:
            return

        for match in ann.pools:
            row: MutableCsvRow = {
                "Symbol": ledger.symbol,
            }

            for header in self.HEADERS:
                fn = self.MAPPINGS_MATCH.get(header)
                if fn is None:
                    if header not in row:
                        row[header] = ""
                    continue

                row[header] = fn(self, transaction, match)

            w.writerow(row)

    def _write_footer(self, f: TextIO, ledger: Ledger, txns: Sequence[Transaction], summary: S104Summary) -> None:
        assert txns, "Transactions should not be empty when writing footer."

        f.write("\n")
        f.write(f"{ledger.symbol} Period {summary.start_date} : {summary.end_date}\n")
        f.write(f"Total Trades: {summary.trades}\n")
        f.write(f"  Acquisitions: {summary.buys}\n")
        f.write(f"  Disposals: {summary.sells}\n")
        f.write(f"Total Realised Gain: {summary.gain!s}\n")
        f.write("\n")

    def _write_summary(self, f: TextIO, summary: S104Summary) -> None:
        f.write("\n")
        f.write("========================================\n")
        f.write(f"Overall Period {summary.start_date} : {summary.end_date}\n")
        f.write(f"Total Trades: {summary.trades}\n")
        f.write(f"  Acquisitions: {summary.buys}\n")
        f.write(f"  Disposals: {summary.sells}\n")
        f.write(f"Total Realised Gain: {summary.gain!s}\n")
        f.write("\n")


COMPONENT = CgtReportExporter
