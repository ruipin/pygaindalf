# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import abstractmethod
from collections.abc import Generator, Mapping, MutableMapping, Sequence
from typing import TYPE_CHECKING, Any, NamedTuple, override

from frozendict import frozendict
from pydantic import Field

from .....portfolio.models.transaction import Transaction
from .....util.helpers.currency import Currency
from .importer import Importer, ImporterConfig


if TYPE_CHECKING:
    from pathlib import Path

    from .....portfolio.models.ledger import Ledger


class CellPosition(NamedTuple):
    row: int
    column: int


class SpreadsheetImporterConfig(ImporterConfig):
    create_ledger: bool = Field(default=False, description="Whether to create a new ledger for the imported data if it does not already exist.")


# MARK: Importer
class SpreadsheetImporter[C: SpreadsheetImporterConfig](Importer[C]):
    # MARK: Properties and Methods to be Implemented by Subclasses
    @property
    def _skip_until(self) -> str | int | tuple[int, int] | None:
        return None

    @property
    @abstractmethod
    def _has_header(self) -> bool:
        msg = "Subclasses must implement the 'has_header' property."
        raise NotImplementedError(msg)

    @property
    @abstractmethod
    def _header_mappings(self) -> Mapping[str | int, str]:
        msg = "Subclasses must implement the '_header_mappings' property."
        raise NotImplementedError(msg)

    @abstractmethod
    def _get_raw_row(self, row: int, *, column_offset: int = 0) -> Sequence[str] | None:
        msg = "Subclasses must implement the '_get_raw_row' method."
        raise NotImplementedError(msg)

    def _get_ticker_from_data(self, data: Mapping[str, Any]) -> str | None:
        return data.get("ticker")

    def _get_isin_from_data(self, data: Mapping[str, Any]) -> str | None:
        return data.get("isin")

    def _get_currency_from_data(self, data: Mapping[str, Any]) -> Currency | None:
        currency = data.get("currency")
        if currency is not None:
            currency = Currency(currency)
        return currency

    @abstractmethod
    def _get_instrument_type_from_data(self, data: Mapping[str, Any]) -> Any:
        msg = "Subclasses must implement the '_get_instrument_type_from_data' method."
        raise NotImplementedError(msg)

    def _should_import_row_data(self, data: Mapping[str, Any]) -> bool:  # noqa: ARG002
        return True

    def _extract_instrument_data(self, data: Mapping[str, Any]) -> MutableMapping[str, Any]:
        return {
            "currency": self._get_currency_from_data(data),
            "type": self._get_instrument_type_from_data(data),
        }

    def _extract_transaction_data(self, data: Mapping[str, Any]) -> MutableMapping[str, Any]:
        return {k: v for k, v in data.items() if k not in {"ticker", "isin", "currency"}}

    # MARK: Internal Methods
    def _get_ledger(self, *, data: Mapping[str, Any], ticker: str | None = None, isin: str | None = None) -> Ledger:
        ledger = self.get_ledger(ticker=ticker, isin=isin)
        if ledger is not None:
            return ledger

        if self.config.create_ledger:
            instrument_data = self._extract_instrument_data(data)
            return self.get_or_create_ledger(ticker=ticker, isin=isin, **instrument_data)

        msg = f"Could not find {'or create ' if self.config.create_ledger else ''}ledger for instrument with {ticker=}, {isin=}."
        raise ValueError(msg)

    def _get_row(self, row: int) -> Sequence[str] | None:
        return self._get_raw_row(self.offset.row + row, column_offset=self.offset.column)

    def _iterate_rows(self, *, start: int = 0) -> Generator[Sequence[str]]:
        row_i = start
        while True:
            row = self._get_row(row_i)
            if row is None:
                break
            yield row
            row_i += 1

    def _get_start_offset(self) -> CellPosition:
        skip_until = self._skip_until

        if skip_until is None:
            return CellPosition(row=0, column=0)
        elif isinstance(skip_until, int):
            return CellPosition(row=skip_until, column=0)
        elif isinstance(skip_until, tuple):
            if len(skip_until) != 2 or not all(isinstance(i, int) for i in skip_until):  # noqa: PLR2004
                msg = "'skip_until' tuple must contain exactly two integers."
                raise TypeError(msg)
            return CellPosition(row=skip_until[0], column=skip_until[1])
        elif not isinstance(skip_until, str):
            msg = "'skip_until' must be of type 'str', 'int', or 'None'."
            raise TypeError(msg)

        # Search for the cell 'skip_until'

        row_i = 0
        while True:
            row = self._get_raw_row(row_i)
            if row is None:
                break

            for column_i, cell in enumerate(row):
                if cell == skip_until:
                    return CellPosition(row=row_i, column=column_i)

            row_i += 1

        msg = f"Could not find cell with value '{skip_until}'."
        raise ValueError(msg)

    def _allow_missing_column(self, column: str) -> bool:  # noqa: ARG002
        return False

    def _get_column_mappings(self) -> Mapping[int, str]:
        result = {}
        mappings = self._header_mappings

        header = self._get_row(0) if self._has_header else None

        for key, value in mappings.items():
            if isinstance(key, int):
                result[key] = value

            elif isinstance(key, str):
                if header is None:
                    msg = "Cannot use string keys for header mappings when there is no header."
                    raise ValueError(msg)

                try:
                    column_i = header.index(key)
                except ValueError:
                    if self._allow_missing_column(key):
                        continue
                    msg = f"Could not find header column with name '{key}'."
                    raise ValueError(msg) from None

                result[column_i] = value

            else:
                msg = "Header mapping keys must be either 'int' or 'str'."
                raise TypeError(msg)

        return frozendict(result)

    def _parse_row(self, row: Sequence[str]) -> Mapping[str, Any]:
        data = {}
        mappings = self.column_mappings

        for column_i, attr in mappings.items():
            if column_i > len(row):
                msg = f"Row does not have column index {column_i}."
                raise IndexError(msg)

            data[attr] = row[column_i]

        return data

    def _import_row_data(self, data: Mapping[str, Any]) -> None:
        ticker = self._get_ticker_from_data(data)
        isin = self._get_isin_from_data(data)
        ledger = self._get_ledger(ticker=ticker, isin=isin, data=data)

        self._import_transaction(ledger, data)

    def _import_transaction(self, ledger: Ledger, data: Mapping[str, Any]) -> None:
        txn_data = self._extract_transaction_data(data)

        txn = Transaction(**txn_data)
        ledger.journal.transactions.add(txn)

    def _process_row(self, row: Sequence[str]) -> None:
        data = self._parse_row(row)
        if self._should_import_row_data(data):
            self._import_row_data(data)

    def process(self) -> None:
        self.offset = self._get_start_offset()
        self.column_mappings = self._get_column_mappings()

        for row in self._iterate_rows(start=1 if self._has_header else 0):
            self._process_row(row)


class BaseCsvSpreadsheetImporter[C: SpreadsheetImporterConfig](SpreadsheetImporter[C]):
    # MARK: Properties and Methods to be Implemented by Subclasses
    def _get_csv_dialect(self) -> str:
        msg = "Subclasses must implement the '_get_csv_dialect' method."
        raise NotImplementedError(msg)

    def open(self, filepath: Path) -> None:
        import csv

        with filepath.open("r", newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile, dialect=self._get_csv_dialect())
            self._csv_rows = list(reader)

    @override
    def _get_raw_row(self, row: int, *, column_offset: int = 0) -> Sequence[str] | None:
        if row < 0 or row >= len(self._csv_rows):
            return None

        raw_row = self._csv_rows[row]
        if column_offset > 0:
            raw_row = raw_row[column_offset:]

        return raw_row
