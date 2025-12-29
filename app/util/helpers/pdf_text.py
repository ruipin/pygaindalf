# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import decimal
import re

from pathlib import Path
from typing import TYPE_CHECKING

import pdfplumber

from .decimal_currency import DecimalCurrency


if TYPE_CHECKING:
    from .currency import Currency


class PdfText:
    def __init__(self, pdf_path: str | Path) -> None:
        self.pdf_path = Path(pdf_path)
        self.text = self._extract_text()

    def _extract_text(self) -> str:
        """Extract text from a (non-scanned) PDF. Joins all pages into one string."""
        chunks: list[str] = []
        with pdfplumber.open(str(self.pdf_path)) as pdf:
            chunks.extend(page.extract_text() or "" for page in pdf.pages)

        # Normalize NBSP and ensure stable newlines
        return "\n".join(chunks).replace("\u00a0", " ")

    def search(self, pattern: str | re.Pattern) -> re.Match | None:
        """Return the capture groups for `pattern` in `self.text`, else None."""
        return re.search(pattern, self.text, flags=re.MULTILINE if isinstance(pattern, str) else 0)

    def expect(self, pattern: str | re.Pattern) -> str:
        """Return the first (and only) capture group for `pattern` in `self.text`, else fail loudly."""
        m = self.search(pattern)

        if not m:
            msg = f"Missing expected pattern: {pattern!r}"
            raise ValueError(msg)

        if m.lastindex != 1:
            msg = f"Expected exactly one capture group for pattern: {pattern!r}, found {m.lastindex}"
            raise ValueError(msg)

        return m.group(1)

    def expect_int(self, pattern: str | re.Pattern, *, thousands_separator: str | None = ",") -> int:
        """Return the single capture group as int for `pattern` in `self.text`, else fail loudly."""
        str_value = self.expect(pattern)

        if thousands_separator:
            str_value = str_value.replace(thousands_separator, "")

        try:
            return int(str_value)
        except ValueError as e:
            msg = f"Expected integer for pattern: {pattern!r}, found {str_value!r}"
            raise ValueError(msg) from e

    def expect_decimal(self, pattern: str | re.Pattern, *, thousands_separator: str | None = ",", decimal_separator: str | None = ".") -> decimal.Decimal:
        """Return the single capture group as Decimal for `pattern` in `self.text`, else fail loudly."""
        str_value = self.expect(pattern)

        if thousands_separator:
            str_value = str_value.replace(thousands_separator, "")
        if decimal_separator and decimal_separator != ".":
            str_value = str_value.replace(decimal_separator, ".")

        try:
            return decimal.Decimal(str_value)
        except decimal.InvalidOperation as e:
            msg = f"Expected decimal for pattern: {pattern!r}, found {str_value!r}"
            raise ValueError(msg) from e

    def expect_decimal_currency(
        self, pattern: str | re.Pattern, currency: str | Currency, *, thousands_separator: str | None = ",", decimal_separator: str | None = "."
    ) -> DecimalCurrency:
        """Return the single capture group as DecimalCurrency for `pattern` in `self.text`, else fail loudly."""
        dec = self.expect_decimal(pattern, thousands_separator=thousands_separator, decimal_separator=decimal_separator)
        return DecimalCurrency(dec, currency=currency)

    def __contains__(self, substring: str) -> bool:
        return substring in self.text
