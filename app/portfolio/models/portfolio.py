# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override, TYPE_CHECKING, Iterator, Iterable
from pydantic import Field
from functools import cached_property
from collections.abc import MutableSet, Set

from .entity import Entity
from .ledger.ledger import Ledger
from .instrument import Instrument
from .uid import Uid

from .entity import IncrementingUidEntity

from ..collections.ordered_view import OrderedViewSet
from .ledger import UidProxyOrderedViewLedgerSet, OrderedViewFrozenLedgerUidSet


class Portfolio(IncrementingUidEntity, MutableSet[Ledger]):
    # Make type checkers believe that the ledger_uids tuple is mutable
    if TYPE_CHECKING:
        ledger_uids_ : Iterable[Uid] = Field(default_factory=OrderedViewFrozenLedgerUidSet, alias='ledger_uids')
        @property
        def ledger_uids(self) -> OrderedViewSet[Uid]: ...
        @ledger_uids.setter
        def ledger_uids(self, value : MutableSet[Uid] | Set[Uid]) -> None: ...
    else:
        ledger_uids : OrderedViewFrozenLedgerUidSet = Field(default_factory=OrderedViewFrozenLedgerUidSet, description="A set of ledger Uids associated with this portfolio.")

    @cached_property
    def ledgers(self) -> UidProxyOrderedViewLedgerSet:
        return UidProxyOrderedViewLedgerSet(owner=self, field='ledger_uids')


    # MARK: Custom __getitem__
    #def __getitem__(self, index : int) -> Ledger:
    #    return self.ledgers[index]


    # MARK: Custom __getitem__
    def __getitem__(self, index : int | Uid | Instrument) -> Ledger:
        ledger = None

        if isinstance(index, int):
            return self.ledgers[index]

        if isinstance(index, Uid):
            if (entity := Entity.by_uid(index)) is None:
                raise KeyError(f"Entity with UID {index} not found")

            if isinstance(entity, Ledger):
                if entity.uid not in self.ledger_uids:
                    raise KeyError(f"Ledger with UID {index} not found in portfolio")
                return entity
            elif not isinstance(entity, Instrument):
                raise KeyError(f"Instrument with UID {index} not found in portfolio")
            index = entity

        if isinstance(index, Instrument):
            if (ledger := Ledger.by_instrument(index)) is None:
                raise KeyError(f"Ledger for index '{index}' not found")
            return ledger

        raise KeyError(f"Index must be an int, Uid or Instrument, got {type(index).__name__}")


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
    def __iter__(self) -> Iterator[Ledger]: # pyright: ignore[reportIncompatibleMethodOverride] since we are overriding the pydantic BaseModel iterator on purpose
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