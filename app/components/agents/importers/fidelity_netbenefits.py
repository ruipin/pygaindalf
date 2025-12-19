# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime
import glob
import os

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from iso4217 import Currency
from pydantic import Field

from ....portfolio.models.transaction import Transaction, TransactionType
from ....util.helpers.pdf_text import PdfText
from .importer import SchemaImporter, SchemaImporterConfig


if TYPE_CHECKING:
    from ....portfolio.models.ledger import Ledger


class TransactionKind(StrEnum):
    VEST = "VEST"
    ESPP = "ESPP"
    SALE = "SALE"


class FidelityNetbenefitsImporterConfig(SchemaImporterConfig):
    glob: str = Field(description="The glob pattern to all Fidelity Netbenefits Trade Confirmation PDF files")
    currency: Currency = Field(default=Currency("USD"), description="The currency of the transactions being imported")


# MARK: Importer
class FidelityNetbenefitsImporter(SchemaImporter[FidelityNetbenefitsImporterConfig]):
    _MONTHS: ClassVar[dict[str, int]] = {
        "JAN": 1,
        "FEB": 2,
        "MAR": 3,
        "APR": 4,
        "MAY": 5,
        "JUN": 6,
        "JUL": 7,
        "AUG": 8,
        "SEP": 9,
        "OCT": 10,
        "NOV": 11,
        "DEC": 12,
    }

    def _parse_date(self, date_str: str) -> datetime.date:
        """Parse Fidelity NetBenefits date strings of the form 'AUG/29/2025' into a datetime.date.

        Fail loudly if the format is unexpected.
        """
        try:
            month_abbr, day_str, year_str = date_str.split("/")
        except ValueError as e:
            msg = f"Invalid date format (expected MON/DD/YYYY): {date_str!r}"
            raise ValueError(msg) from e

        month = self._MONTHS.get(month_abbr.upper())
        if month is None:
            msg = f"Invalid month abbreviation in date: {date_str!r}"
            raise ValueError(msg)

        try:
            day = int(day_str)
            year = int(year_str)
        except ValueError as e:
            msg = f"Invalid numeric component in date: {date_str!r}"
            raise ValueError(msg) from e

        return datetime.date(year, month, day)

    def _get_kind(self, pdf: PdfText) -> TransactionKind:
        """Detect whether this trade confirmation PDF relates to a vest/distribution or a sale.

        Uses semantic anchors rather than layout.
        """
        # ESPP purchase confirmations
        if "STOCK PURCHASE PLAN" in pdf and "YOU PURCHASED" in pdf:
            return TransactionKind.ESPP

        # VEST / RSU distribution confirmations
        if "DISTRIBUTION DETAILS" in pdf and "SHARES WERE DISTRIBUTED" in pdf:
            return TransactionKind.VEST

        # SALE confirmations
        if "Sale Date:" in pdf and "YOU SOLD" in pdf:
            return TransactionKind.SALE

        msg = "Unknown PDF kind (not VEST, SALE, or ESPP)"
        raise ValueError(msg)

    def _get_ledger(self, symbol: str) -> Ledger:
        ledger = self.context.get_ledger(ticker=symbol)
        if ledger is None:
            msg = f"Could not find ledger for instrument with ticker symbol: {symbol}"
            raise ValueError(msg)
        return ledger

    def _parse_espp(self, pdf: PdfText) -> None:
        # Symbol
        symbol = pdf.expect(r"SECURITY DESCRIPTION SYMBOL:\s*([A-Z0-9.\-]+)")

        # Date
        date_str = pdf.expect(r"Confirmation of purchase made through your\s+.+\s+on\s+([A-Z]{3}/\d{2}/\d{4})\.")
        date = self._parse_date(date_str)

        # Quantity
        quantity = pdf.expect_decimal(r"YOU PURCHASED\s+(\d[\d,]*)\s+AT")

        # Purchase price
        purchase_price = pdf.expect_decimal_currency(r"YOU PURCHASED\s+.+\s+AT\s+\$(\d[\d,]*\.\d+)\s+PURCHASE PRICE", currency=self.config.currency)

        # FMV
        fmv_total = pdf.expect_decimal_currency(r"Market\s+Value\s+at\s+Purchase[^\d$]*\$\s*(\d[\d,]*\.\d+)", currency=self.config.currency)
        fmv_unit = fmv_total / quantity

        # Discount
        discount_unit = fmv_unit - purchase_price
        discount_total = discount_unit * quantity

        ####
        # Import Transaction
        ledger = self._get_ledger(symbol)

        txn = Transaction(
            type=TransactionType.VEST,
            date=date,
            quantity=quantity,
            consideration=fmv_total,
            discount=discount_total,
        )

        ledger.journal.transactions.add(txn)

    def _parse_vest(self, pdf: PdfText) -> None:
        # Symbol
        symbol = pdf.expect(r"SYMBOL:\s*([A-Z0-9.\-]+)")

        # Date
        date_str = pdf.expect(r"Date of Distribution:\s*([A-Z]{3}/\d{2}/\d{4})")
        date = self._parse_date(date_str)

        # Shares
        shares_gross = pdf.expect_decimal(r"(\d[\d,]*)\s+SHARES WERE DISTRIBUTED")
        shares_tax = pdf.expect_decimal(r"(\d[\d,]*)\s+SHARES WERE NETTED TO COVER YOUR TAX")
        shares_net = shares_gross - shares_tax
        if shares_net <= 0:
            msg = f"Invalid net shares: {shares_gross} - {shares_tax} = {shares_net}"
            raise ValueError(msg)

        # FMV
        fmv_unit = pdf.expect_decimal_currency(r"Fair Market Value:\s*\$(\d[\d,]*\.\d+)", currency=self.config.currency)
        fmv_total = fmv_unit * shares_net

        ####
        # Import Transaction
        ledger = self._get_ledger(symbol)

        txn = Transaction(
            type=TransactionType.VEST,
            date=date,
            quantity=shares_net,
            consideration=fmv_total,
        )

        ledger.journal.transactions.add(txn)

    def _parse_sale(self, pdf: PdfText) -> None:
        # Symbol
        symbol = pdf.expect(r"SYMBOL:\s*([A-Z0-9.\-]+)")

        # Date
        date_str = pdf.expect(r"Sale Date:\s*([A-Z]{3}/\d{2}/\d{4})")
        date = self._parse_date(date_str)

        # Shares
        quantity = pdf.expect_decimal(r"YOU SOLD\s+(\d[\d,]*)\s+AT")

        # Proceeds + fees ---
        proceeds_gross = pdf.expect_decimal_currency(r"Sale Proceeds\s+\$(\d[\d,]*\.\d+)", currency=self.config.currency)
        fees = pdf.expect_decimal_currency(r"Total Fees\s+\$(\d[\d,]*\.\d+)", currency=self.config.currency)

        proceeds_net = proceeds_gross - fees
        if proceeds_net < 0:
            msg = f"Net proceeds computed negative: {proceeds_net}"
            raise ValueError(msg)

        ####
        # Import Transaction
        ledger = self._get_ledger(symbol)

        txn = Transaction(
            type=TransactionType.SELL,
            date=date,
            quantity=quantity,
            consideration=proceeds_net,
            fees=fees,
        )

        ledger.journal.transactions.add(txn)

    def _process_pdf(self, path: Path) -> None:
        try:
            pdf = PdfText(path)

            kind = self._get_kind(pdf)

            if kind is TransactionKind.VEST:
                self._parse_vest(pdf)
            elif kind is TransactionKind.SALE:
                self._parse_sale(pdf)
            elif kind is TransactionKind.ESPP:
                self._parse_espp(pdf)
            else:
                msg = f"Unhandled NetBenefits confirmation type: {kind}"
                raise NotImplementedError(msg)  # noqa: TRY301

        except Exception as e:
            msg = f"Error processing PDF '{path}': {e}"
            raise RuntimeError(msg) from e

    @override
    def _do_run(self) -> None:
        paths = sorted(Path(p) for p in glob.glob(os.path.expandvars(self.config.glob)))  # noqa: PTH207
        if not paths:
            msg = f"No PDFs matched glob: {self.config.glob}"
            raise FileNotFoundError(msg)

        with self.session(f"Fidelity NetBenefits Importer for {self.config.glob}"):
            for path in paths:
                self._process_pdf(path)


COMPONENT = FidelityNetbenefitsImporter
