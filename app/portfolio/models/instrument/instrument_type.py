# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from enum import StrEnum
from typing import override


class InstrumentType(StrEnum):
    # fmt: off
    EQUITY = "equity"
    ETF    = "etf"
    FUND   = "fund"
    BOND   = "bond"
    OPTION = "option"
    FUTURE = "future"
    FOREX  = "forex"
    CRYPTO = "crypto"
    OTHER  = "other"
    # fmt: on

    # MARK: Stock & Derivatives
    @property
    def is_stock(self) -> bool:
        return self in {
            InstrumentType.EQUITY,
            InstrumentType.ETF,
            InstrumentType.FUND,
        }

    @property
    def is_fund(self) -> bool:
        return self in {
            InstrumentType.FUND,
            InstrumentType.ETF,
        }

    @property
    def is_derivative(self) -> bool:
        return self in {
            InstrumentType.OPTION,
            InstrumentType.FUTURE,
        }

    # MARK: Utilities
    @override
    def __str__(self) -> str:
        return self.value

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.name}"
