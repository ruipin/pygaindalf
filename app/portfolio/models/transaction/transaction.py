# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref

from typing import TYPE_CHECKING, Any

from pydantic import field_validator

from ....util.helpers.empty_class import empty_class
from ..entity import Entity, IncrementingUidMixin
from .transaction_impl import TransactionImpl
from .transaction_journal import TransactionJournal
from .transaction_record import TransactionRecord


class Transaction(
    TransactionImpl if TYPE_CHECKING else empty_class(),
    IncrementingUidMixin,
    Entity[TransactionRecord, TransactionJournal],
    init=False,
    unsafe_hash=True,
):
    @field_validator("instance_parent_weakref", mode="before")
    @classmethod
    def _validate_instance_parent_is_ledger(cls, value: Any) -> Any:
        from ..ledger import Ledger

        if value is None:
            return value

        parent = value() if isinstance(value, weakref.ref) else value
        if parent is not None and not isinstance(parent, Ledger):
            msg = f"Transaction.instance_parent must be a Ledger, got {type(value).__name__}."
            raise ValueError(msg)

        return value


TransactionRecord.register_entity_class(Transaction)
