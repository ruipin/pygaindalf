# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override

from enum import StrEnum


class TransactionType(StrEnum):
    # TODO: We might want to subclass transaction types for more specific behavior, e.g. AcquisitionTransaction vs DisposalTransaction ?
    BUY      = "buy"
    SELL     = "sell"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    FEE      = "fee"

    @override
    def __str__(self) -> str:
        return self.value

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.name}"