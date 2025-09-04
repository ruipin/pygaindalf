# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override, Annotated, overload, Literal, Any, TYPE_CHECKING, Iterator
from pydantic import Field, PrivateAttr, field_validator
from functools import cached_property
from collections.abc import MutableSet, Set

from .models.entity import Entity
from .models.ledger import Ledger
from .models.instrument import Instrument
from .models.uid import Uid

from .models.entity import IncrementingUidEntity

from .journal.session_manager import SessionManager
from .collections.uid_proxy import UidProxySet


# Specialize explicitly in order for type introspection to work
class UidProxyLedgerSet(UidProxySet[Ledger]):
    pass


class Portfolio(MutableSet[Ledger | Uid], IncrementingUidEntity):
    # MARK: Ledgers
    # Make type checkers believe that the ledgers set is mutable
    if TYPE_CHECKING:
        ledger_uids_ : frozenset[Uid] = Field(default_factory=frozenset, alias='ledger_uids')
        @property
        def ledger_uids(self) -> MutableSet[Uid]: ...
        @ledger_uids.setter
        def ledger_uids(self, value : MutableSet[Uid] | Set[Uid]) -> None: ...
    else:
        ledger_uids : frozenset[Uid] = Field(default_factory=frozenset, description="A mapping of Instrument UIDs to Ledger instances.")

    @field_validator('ledger_uids', mode='before')
    @classmethod
    def _validate_transaction_uids(cls, value : Any):
        if not isinstance(value, Set):
            raise TypeError(f"Expected 'transaction_uids' to be a Set, got {type(value).__name__}.")

        ledger_ns = Ledger.uid_namespace()
        for uid in value:
            if not isinstance(uid, Uid):
                raise TypeError(f"Expected 'transaction_uids' elements to be Uid instances, got {type(uid).__name__}.")
            if uid.namespace != ledger_ns:
                raise ValueError(f"Invalid transaction UID namespace: expected '{ledger_ns}', got '{uid.namespace}'.")

        return value

    @cached_property
    def ledgers(self) -> MutableSet[Ledger]:
        return UidProxyLedgerSet(owner=self, field='ledger_uids')


    # MARK: Custom __getitem__
    def __getitem__(self, index : Uid | Instrument) -> Ledger:
        ledger = None

        if isinstance(index, Uid):
            entity = Entity.by_uid(index)
            if entity is None:
                raise KeyError(f"Entity with UID {index} not found")

            if isinstance(entity, Ledger):
                ledger = entity
            elif isinstance(entity, Instrument):
                index = entity
            else:
                raise TypeError(f"Expected UID '{index}' to reference a Ledger or Instrument, got {type(entity).__name__}")

        if isinstance(index, Instrument):
            ledger = Ledger.by_instrument(index)

        if ledger is None:
            raise KeyError(f"Ledger for index '{index}' not found")

        return ledger


    # MARK: MutableSet ABC
    @override
    def __contains__(self, value : object) -> bool:
        if not isinstance(value, (Ledger, Uid)):
            return False
        return Ledger.narrow_to_uid(value) in self.ledger_uids

    @override
    def add(self, value : Ledger | Uid) -> None:
        self.ledger_uids.add(Ledger.narrow_to_uid(value))

    @override
    def discard(self, value : Ledger | Uid) -> None:
        self.ledger_uids.discard(Ledger.narrow_to_uid(value))

    @override
    def __iter__(self) -> Iterator[Ledger]: # pyright: ignore[reportIncompatibleMethodOverride] since the narrowing is on purpose
        for uid in self.ledger_uids:
            ledger = Ledger.by_uid(uid)
            if ledger is None:
                raise KeyError(f"Ledger with UID {uid} not found")
            yield ledger

    @override
    def __len__(self):
        return len(self.ledger_uids)

    @override
    def __repr__(self) -> str:
        return super().__repr__().replace('>', f", ledgers={repr(self.ledger_uids)}>")