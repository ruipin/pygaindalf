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
from .importer import BaseCsvSpreadsheetImporter, SpreadsheetImporterConfig


class InteractiveBrokersImporterConfig(SpreadsheetImporterConfig):
    glob: str = Field(description="The glob pattern to all Interactive Brokers CSV files")


# MARK: Importer
class InteractiveBrokersImporter(BaseCsvSpreadsheetImporter[InteractiveBrokersImporterConfig]):
    HEADER_MAPPINGS: ClassVar[Mapping[str | int, str]] = {
        "DataDiscriminator": "discriminator",
        "Asset Category": "asset_category",
        "Currency": "currency",
        "Symbol": "ticker",
        "Date/Time": "datetime",
        "Quantity": "quantity",
        "Proceeds": "consideration",
        "Comm/Fee": "fees",
    }

    @override
    def _get_csv_dialect(self) -> str:
        return "excel"

    @property
    @override
    def _skip_until(self) -> str | int | tuple[int, int] | None:
        return "Trades"

    @property
    @override
    def _has_header(self) -> bool:
        return True

    @property
    @override
    def _header_mappings(self) -> Mapping[str | int, str]:
        return self.__class__.HEADER_MAPPINGS

    @override
    def _should_import_row_data(self, data: Mapping[str, Any]) -> bool:
        return data["discriminator"] == "Trade" and data["asset_category"] != "Forex"

    @override
    def _get_instrument_type_from_data(self, data: Mapping[str, Any]) -> Any:
        itype = data.get("asset_category")

        if itype == "Equity and Index Options":
            return InstrumentType.OPTION
        # TODO: Add more mappings as needed
        else:
            msg = f"Unsupported instrument type '{itype}' encountered during import."
            raise ValueError(msg)

    def _get_data(self, data: Mapping[str, Any], key: str) -> Any:
        value = data.get(key)
        if value is None:
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
        date_str = datetime_str.split(", ")[0]
        date = datetime.date.strptime(date_str, "%Y-%m-%d")

        # Quantity
        quantity_str = self._get_data(data, "quantity")
        quantity = self.decimal(quantity_str)

        # Transaction Type
        transaction_type = TransactionType.BUY if quantity > 0 else TransactionType.SELL
        quantity = abs(quantity)

        # Consideration
        consideration_str = self._get_data(data, "consideration")
        consideration = self.decimal(consideration_str, currency=currency)
        consideration = abs(consideration)

        # Fees
        fees_str = self._get_data(data, "fees")
        fees = -self.decimal(fees_str, currency=currency)

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

        with self.session(f"Interactive Brokers CSV Importer for {self.config.glob}"):
            for path in paths:
                self.open(path)
                self.process()


COMPONENT = InteractiveBrokersImporter
