# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import TYPE_CHECKING, override

from ....util.helpers.empty_class import empty_class
from ..entity import EntityRecord
from .transaction_impl import TransactionImpl
from .transaction_journal import TransactionJournal
from .transaction_schema import TransactionSchema


if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison


class TransactionRecord(
    TransactionImpl,
    TransactionSchema if not TYPE_CHECKING else empty_class(),
    EntityRecord[TransactionJournal],
    init=False,
    unsafe_hash=True,
):
    # MARK: Utilities
    @override
    def sort_key(self) -> SupportsRichComparison:
        return (self.date, self.uid)
