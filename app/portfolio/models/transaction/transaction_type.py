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

    @override
    def __str__(self) -> str:
        return self.value

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.name}"
