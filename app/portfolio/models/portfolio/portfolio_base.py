# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from functools import cached_property

from collections.abc import Set
from abc import abstractmethod, ABCMeta
from typing import override, Iterator, TYPE_CHECKING

from ....util.helpers.empty_class import EmptyClass
from ....util.helpers import generics

from ..uid import Uid
from ..ledger import Ledger, UidProxyOrderedViewLedgerFrozenSet
from ..entity import Entity, EntityBase
from ..instrument import Instrument

from .portfolio_fields import PortfolioFields


class PortfolioBase[
    T_Uid_Set : Set[Uid],
    T_Proxy_Set : UidProxyOrderedViewLedgerFrozenSet
](
    EntityBase,
    PortfolioFields[T_Uid_Set] if TYPE_CHECKING else EmptyClass,
    Set[Ledger],
    metaclass=ABCMeta
):
    # MARK: Ledgers
    get_proxy_set_type = generics.GenericIntrospectionMethod[T_Proxy_Set]()

    @cached_property
    def ledgers(self) -> T_Proxy_Set:
        return self.get_proxy_set_type(origin=True)(owner=self, field='ledger_uids')

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