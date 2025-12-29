# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


import dataclasses
import datetime

from collections.abc import Callable, Mapping, MutableMapping, MutableSequence, Sequence
from csv import DictWriter
from typing import TYPE_CHECKING, ClassVar, TextIO, override

from pydantic import Field

from app.portfolio.models.transaction import Transaction

from ....util.config.models.env_path import EnvForceNewPath
from ....util.helpers.currency import S104_CURRENCY
from ....util.helpers.decimal_currency import DecimalCurrency
from .exporter import DateFilteredExporter, DateFilteredExporterConfig


if TYPE_CHECKING:
    from decimal import Decimal

    from ....portfolio.models.annotation.s104.s104_holdings_annotation import S104HoldingsAnnotation
    from ....portfolio.models.annotation.s104.s104_pool_annotation import S104Pool
    from ....portfolio.models.ledger import Ledger
    from ....portfolio.models.transaction import Transaction

type CsvCell = str | int | Decimal
type MutableCsvRow = MutableMapping[str, CsvCell]


# MARK: Configuration
class S104ReportExporterConfig(DateFilteredExporterConfig):
    filepath: EnvForceNewPath = Field(description="The file to export the portfolio data to")

    cost_precision: int = Field(default=2, description="The number of decimal places for S104 costs.")


# Utility class
@dataclasses.dataclass
class S104TaxYear:
    start_year: int

    buys: int = 0
    sells: int = 0

    losses: DecimalCurrency = dataclasses.field(default_factory=lambda: DecimalCurrency(0, currency=S104_CURRENCY))
    gains: DecimalCurrency = dataclasses.field(default_factory=lambda: DecimalCurrency(0, currency=S104_CURRENCY))

    transactions: MutableSequence[Transaction] = dataclasses.field(default_factory=list)

    @property
    def start_date(self) -> datetime.date:
        return datetime.date(self.start_year, 4, 6)

    @property
    def end_year(self) -> int:
        return self.start_year + 1

    @property
    def end_date(self) -> datetime.date:
        return datetime.date(self.end_year, 4, 5)

    @property
    def name(self) -> str:
        return f"{self.start_year}-{str(self.end_year)[-2:]}"

    @property
    def trades(self) -> int:
        return self.buys + self.sells

    @property
    def result(self) -> DecimalCurrency:
        return self.gains - self.losses

    def merge(self, other: S104TaxYear) -> None:
        assert self.start_year == other.start_year, "Can only merge tax years with the same start year."

        self.buys += other.buys
        self.sells += other.sells
        self.gains += other.gains
        self.losses += other.losses
        self.transactions.extend(other.transactions)

    def add_transaction(self, transaction: Transaction, cost_precision: int) -> None:
        assert transaction.date >= self.start_date, f"Transaction date {transaction.date} is before tax year start date {self.start_date}."
        assert transaction.date <= self.end_date, f"Transaction date {transaction.date} is after tax year end date {self.end_date}."

        self.transactions.append(transaction)

        if transaction.type.acquisition:
            self.buys += 1
        elif transaction.type.disposal:
            self.sells += 1

            gain = round(transaction.get_s104_capital_gain(), cost_precision)
            if gain >= 0:
                self.gains += gain
            else:
                self.losses += -gain


@dataclasses.dataclass
class S104Summary:
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None

    tax_years: dict[int, S104TaxYear] = dataclasses.field(default_factory=dict)

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

    def _get_or_create_tax_year(self, year: int) -> S104TaxYear:
        if year not in self.tax_years:
            self.tax_years[year] = S104TaxYear(start_year=year)
        return self.tax_years[year]

    def add_transaction(self, transaction: Transaction, cost_precision: int) -> None:
        self.add_date(transaction.date)

        tax_year_i = transaction.date.year
        if transaction.date < datetime.date(tax_year_i, 4, 6):
            tax_year_i -= 1

        tax_year = self._get_or_create_tax_year(tax_year_i)
        tax_year.add_transaction(transaction, cost_precision)

    def merge(self, other: S104Summary) -> None:
        self._min_first_date(other.start_date)
        self._max_last_date(other.end_date)

        for other_ty in other.tax_years.values():
            ty = self._get_or_create_tax_year(other_ty.start_year)
            ty.merge(other_ty)

    @property
    def trades(self) -> int:
        return sum((ty.trades for ty in self.tax_years.values()), start=0)

    @property
    def buys(self) -> int:
        return sum((ty.buys for ty in self.tax_years.values()), start=0)

    @property
    def sells(self) -> int:
        return sum((ty.sells for ty in self.tax_years.values()), start=0)

    @property
    def gains(self) -> DecimalCurrency:
        return sum((ty.gains for ty in self.tax_years.values()), start=DecimalCurrency(0, currency=S104_CURRENCY))

    @property
    def losses(self) -> DecimalCurrency:
        return sum((ty.losses for ty in self.tax_years.values()), start=DecimalCurrency(0, currency=S104_CURRENCY))

    @property
    def result(self) -> DecimalCurrency:
        return self.gains - self.losses


# MARK: Exporter
class S104ReportExporter(DateFilteredExporter[S104ReportExporterConfig]):
    MAPPINGS_TXN: ClassVar[Mapping[Callable[[Transaction], bool], Mapping[str, Callable[[S104ReportExporter, Transaction], CsvCell]]]] = {
        lambda _txn: True: {
            "ID": lambda _self, txn: f"#{txn.uid.id}",
            "Type": lambda _self, txn: txn.type.name,
            "Date": lambda _self, txn: txn.date.strftime("%Y-%m-%d"),
            "Quantity": lambda _self, txn: txn.quantity,
            "S104 Holdings": lambda _self, txn: txn.get_s104_holdings().quantity,
            "S104 Cumulative Cost": lambda self, txn: round(txn.get_s104_holdings().cumulative_cost, self.config.cost_precision),
        },
        lambda txn: txn.type.trade: {
            "Fees": lambda self, txn: round(txn.get_fees(currency=S104_CURRENCY), self.config.cost_precision),
        },
        lambda txn: txn.type.acquisition: {
            "FMV": lambda self, txn: round(txn.get_consideration(currency=S104_CURRENCY), self.config.cost_precision),
        },
        lambda txn: txn.type.disposal: {
            "S104 Total Cost": lambda self, txn: round(txn.get_s104_total_cost(), self.config.cost_precision),
            "Disposal Proceeds": lambda self, txn: round(txn.get_s104_total_proceeds(), self.config.cost_precision),
            "Gain": lambda self, txn: round(txn.get_s104_capital_gain(), self.config.cost_precision),
        },
    }

    MAPPINGS_MATCH: ClassVar[Mapping[str, Callable[[S104ReportExporter, Transaction, S104Pool], CsvCell]]] = {
        "Match ID": lambda _self, main, pool: f"#{pool.acquisition.uid.id}" if main is pool.disposal else f"#{pool.disposal.uid.id}",
        "Match Date": lambda _self, main, pool: pool.acquisition.date.strftime("%Y-%m-%d")
        if main is pool.disposal
        else pool.disposal.date.strftime("%Y-%m-%d"),
        "Match Quantity": lambda _self, _main, pool: pool.quantity,
        "Match Cost": lambda self, _main, pool: round(pool.total_cost, self.config.cost_precision),
        "Match Proceeds": lambda self, _main, pool: round(pool.total_proceeds, self.config.cost_precision),
    }

    MAPPINGS_HOLDINGS: ClassVar[Mapping[str, Callable[[S104ReportExporter, S104HoldingsAnnotation | None], CsvCell]]] = {
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
                    summary.merge(ledger_summary)

            self._write_summary(f, summary)

    def _process_ledger(self, f: TextIO, ledger: Ledger) -> S104Summary | None:
        txns = self._get_transactions(ledger)
        if not txns:
            return None
        if not any(txn.type.trade for txn in txns):
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

        holdings = txns[0].get_previous_s104_holdings_or_none()
        if holdings is not None and holdings.quantity > 0:
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
        assert transaction.type.trade or transaction.type.stock_split, f"Transaction must be trade or a stock split, got {transaction.type}."

        return True

    def _process_transaction(self, w: DictWriter, ledger: Ledger, transaction: Transaction, summary: S104Summary) -> None:
        summary.add_transaction(transaction, self.config.cost_precision)

        # Sell Transaction
        self._write_transaction(w, ledger, transaction)

        # Matches
        self._write_matches(w, ledger, transaction)

    def _write_transaction(self, w: DictWriter, ledger: Ledger, transaction: Transaction) -> None:
        row: MutableCsvRow = {
            "Symbol": ledger.symbol,
        }

        mappings = {}
        for predicate, mapping in self.MAPPINGS_TXN.items():
            if predicate(transaction):
                mappings.update(mapping)

        for header in self.HEADERS:
            fn = mappings.get(header)
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
        f.write(f"Overall Result: {summary.result!s}\n")
        f.write(f"  Total Gains: {summary.gains!s}\n")
        f.write(f"  Total Losses: {summary.losses!s}\n")
        f.write("\n")

    def _write_summary(self, f: TextIO, summary: S104Summary) -> None:
        f.write("\n")
        f.write("========================================\n")
        f.write(f"Overall Period {summary.start_date} : {summary.end_date}\n")
        f.write(f"Total Trades: {summary.trades}\n")
        f.write(f"  Acquisitions: {summary.buys}\n")
        f.write(f"  Disposals: {summary.sells}\n")
        f.write(f"Overall Result: {summary.result!s}\n")
        f.write(f"  Total Gains: {summary.gains!s}\n")
        f.write(f"  Total Losses: {summary.losses!s}\n")
        f.write("\n")

        for ty in sorted(summary.tax_years.values(), key=lambda ty: ty.start_year):
            f.write("----------------------------------------\n")
            f.write(f"Tax Year {ty.name} ({ty.start_date} : {ty.end_date})\n")
            f.write(f"  Trades: {ty.trades}\n")
            f.write(f"    Acquisitions: {ty.buys}\n")
            f.write(f"    Disposals: {ty.sells}\n")
            f.write(f"  Result: {ty.result!s}\n")
            f.write(f"    Gains: {ty.gains!s}\n")
            f.write(f"    Losses: {ty.losses!s}\n")

            # 2024 has special rules where the gain needs to be split in 'until 29/10/2024' and 'from 30/10/2024'
            if ty.start_year == 2024:  # noqa: PLR2004
                threshold = datetime.date(2024, 10, 30)
                until_gains = DecimalCurrency(0, currency=S104_CURRENCY)
                from_gains = DecimalCurrency(0, currency=S104_CURRENCY)

                for txn in ty.transactions:
                    if not txn.type.disposal:
                        continue
                    gain = round(txn.get_s104_capital_gain(), self.config.cost_precision)
                    if gain > 0:
                        if txn.date < threshold:
                            until_gains += gain
                        else:
                            from_gains += gain
                assert ty.gains == until_gains + from_gains, f"Gains split does not add up to total gains, expected {ty.gains} got {until_gains + from_gains}."

                f.write(f"  Gains Split for TY{ty.name}:\n")
                f.write(f"    Gains until 29/10/2024: {until_gains!s}\n")
                f.write(f"    Gains from 30/10/2024: {from_gains!s}\n")

            f.write("\n")


COMPONENT = S104ReportExporter
