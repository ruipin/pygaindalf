# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from enum import StrEnum
from typing import override


class TransactionType(StrEnum):
    # TODO: We might want to subclass transaction types for more specific behavior, e.g. AcquisitionTransaction vs DisposalTransaction ?
    # fmt: off
    BUY      = "buy"
    SELL     = "sell"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    FEE      = "fee"
    # fmt: on

    # MARK: Acquisitions
    @property
    def buy(self) -> bool:
        return self is TransactionType.BUY

    @property
    def acquisition(self) -> bool:
        return self is TransactionType.BUY

    # MARK: Disposals
    @property
    def sell(self) -> bool:
        return self is TransactionType.SELL

    @property
    def disposal(self) -> bool:
        return self is TransactionType.SELL

    # MARK: Income
    @property
    def dividend(self) -> bool:
        return self is TransactionType.DIVIDEND

    @property
    def interest(self) -> bool:
        return self is TransactionType.INTEREST

    @property
    def income(self) -> bool:
        return self in {TransactionType.DIVIDEND, TransactionType.INTEREST}

    # MARK: Expenses
    @property
    def fee(self) -> bool:
        return self is TransactionType.FEE

    @property
    def expense(self) -> bool:
        return self is TransactionType.FEE

    # MARK: S104
    @property
    def affects_s104_holdings(self) -> bool:
        return self in {TransactionType.BUY, TransactionType.SELL}

    # MARK: Utilities
    @override
    def __str__(self) -> str:
        return self.value

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.name}"
