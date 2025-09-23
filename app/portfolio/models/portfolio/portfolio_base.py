# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from functools import cached_property

from collections.abc import Set, Sequence
from abc import abstractmethod, ABCMeta
from typing import override, Iterator, TYPE_CHECKING

from ..uid import Uid
from ..ledger import Ledger, OrderedViewFrozenLedgerUidSet, UidProxyOrderedViewLedgerFrozenSet
from ..entity import Entity
from ..instrument import Instrument


class PortfolioBase[T_Uid_Set : OrderedViewFrozenLedgerUidSet, T_Proxy_Set : UidProxyOrderedViewLedgerFrozenSet](Set[Ledger], metaclass=ABCMeta):
    if TYPE_CHECKING:
        ledger_uids : T_Uid_Set

    @cached_property
    @abstractmethod
    def ledgers(self) -> T_Proxy_Set:
        raise NotImplementedError("Subclasses must implement ledgers property")


    # MARK: Custom __getitem__
    def __getitem__(self, index : int | Uid | Instrument) -> Ledger:
        ledger = None

        if isinstance(index, int):
            return self.ledgers[index]

        if isinstance(index, Uid):
            entity = Entity.by_uid(index)
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


    # MARK: Set ABC
    @override
    def __contains__(self, value : object) -> bool:
        if not isinstance(value, (Ledger, Uid)):
            return False
        return Ledger.narrow_to_uid(value) in self.ledger_uids

    @override
    def __iter__(self) -> Iterator[Ledger]: # pyright: ignore[reportIncompatibleMethodOverride] since we are overriding the pydantic BaseModel iterator on purpose
        return iter(self.ledgers)

    @override
    def __len__(self):
        return len(self.ledger_uids)

    @override
    def __repr__(self) -> str:
        return super().__repr__().replace('>', f", ledgers={repr(self.ledger_uids)}>")