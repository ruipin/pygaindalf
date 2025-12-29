# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


import datetime
import glob
import os

from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Any, ClassVar, override

from pydantic import Field

from ....portfolio.models.instrument.instrument_type import InstrumentType
from ....portfolio.models.transaction.transaction_type import TransactionType
from ....util.helpers.currency import Currency
from .importer import BaseCsvSpreadsheetImporter, SpreadsheetImporterConfig


class Trading212ImporterConfig(SpreadsheetImporterConfig):
    glob: str = Field(description="The glob pattern to all Trading 212 CSV files")


# MARK: Importer
class Trading212Importer(BaseCsvSpreadsheetImporter[Trading212ImporterConfig]):
    HEADER_MAPPINGS: ClassVar[Mapping[str | int, str]] = {
        "Action": "type",
        "Time": "datetime",
        "ISIN": "isin",
        "Ticker": "ticker",
        "No. of shares": "quantity",
        "Price / share": "unit_consideration",
        "Currency (Price / share)": "currency",
        # "Withholding tax": "withholding_tax", # for dividends
        # "Currency (Withholding tax)": "withholding_tax_currency", # for dividends
        "Stamp duty reserve tax": "stamp_duty",  # for UK equities
        "Currency (Stamp duty reserve tax)": "stamp_duty_currency",  # for UK equities
    }

    @override
    def _get_csv_dialect(self) -> str:
        return "excel"

    @property
    @override
    def _has_header(self) -> bool:
        return True

    @property
    @override
    def _header_mappings(self) -> Mapping[str | int, str]:
        return self.__class__.HEADER_MAPPINGS

    @override
    def _allow_missing_column(self, column: str) -> bool:
        return "Stamp duty" in column

    @override
    def _should_import_row_data(self, data: Mapping[str, Any]) -> bool:
        # TODO: Dividend ?
        typ = data["type"]
        return "buy" in typ or "sell" in typ

    @override
    def _get_instrument_type_from_data(self, data: Mapping[str, Any]) -> Any:
        # TODO: What about ETFs etc?
        return InstrumentType.EQUITY

    def _get_data(self, data: Mapping[str, Any], key: str, *, allow_missing: bool = False) -> Any:
        value = data.get(key)
        if value is None and not allow_missing:
            name = self.__class__.HEADER_MAPPINGS.get(key, key)
            msg = f"Missing expected field '{name}' in the imported data."
            raise ValueError(msg)
        return value

    @override
    def _extract_transaction_data(self, data: Mapping[str, Any]) -> MutableMapping[str, Any]:
        # Currency
        currency = self._get_currency_from_data(data)

        # Date
        datetime_str = self._get_data(data, "datetime")
        date_str = datetime_str.split(" ")[0]
        date = datetime.date.strptime(date_str, "%Y-%m-%d")

        # Quantity
        quantity_str = self._get_data(data, "quantity")
        quantity = self.decimal(quantity_str)

        # Transaction Type
        typ = self._get_data(data, "type").lower()
        if "buy" in typ:
            transaction_type = TransactionType.BUY
        elif "sell" in typ:
            transaction_type = TransactionType.SELL
        else:
            msg = f"Unsupported transaction type: {typ}"
            raise ValueError(msg)

        # Consideration
        unit_consideration_str = self._get_data(data, "unit_consideration")
        unit_consideration = self.decimal(unit_consideration_str, currency=currency)
        consideration = unit_consideration * quantity

        # Fees
        stamp_duty_str = self._get_data(data, "stamp_duty", allow_missing=True)
        if stamp_duty_str:
            stamp_duty_currency_str = self._get_data(data, "stamp_duty_currency")
            if not stamp_duty_currency_str:
                msg = "Stamp duty currency is missing."
                raise ValueError(msg)
            stamp_duty_currency = Currency(stamp_duty_currency_str)
            stamp_duty = -self.decimal(stamp_duty_str, currency=stamp_duty_currency)
        else:
            stamp_duty = self.decimal(0, currency=currency)
        fees = stamp_duty  # TODO: Split into separate field?

        return {
            "type": transaction_type,
            "date": date,
            "quantity": quantity,
            "consideration": consideration,
            "fees": fees,
        }

    @override
    def _do_run(self) -> None:
        paths = sorted(Path(p) for p in glob.glob(os.path.expandvars(self.config.glob)))  # noqa: PTH207
        if not paths:
            msg = f"No files matched glob: {self.config.glob}"
            raise FileNotFoundError(msg)

        with self.session(f"Trading 212 CSV Importer for {self.config.glob}"):
            for path in paths:
                self.open(path)
                self.process()


COMPONENT = Trading212Importer
