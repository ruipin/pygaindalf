# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import Iterator
from collections.abc import Set as AbstractSet
from functools import cached_property
from typing import TYPE_CHECKING, override

from ....util.helpers import generics
from ....util.helpers.empty_class import EmptyClass
from ...collections import UidProxyOrderedViewMutableSet
from ...util.uid import Uid
from ..entity import Entity, EntityBase
from ..instrument import Instrument
from ..ledger import Ledger
from .portfolio_fields import PortfolioFields


class PortfolioBase[
    T_Uid_Set: AbstractSet[Uid],
    T_Proxy_Set: UidProxyOrderedViewMutableSet[Ledger],
](
    EntityBase,
    PortfolioFields[T_Uid_Set] if TYPE_CHECKING else EmptyClass,
    AbstractSet[Ledger],
    metaclass=ABCMeta,
):
    # MARK: Ledgers
    get_proxy_set_type = generics.GenericIntrospectionMethod[T_Proxy_Set]()

    @cached_property
    def ledgers(self) -> T_Proxy_Set:
        return self.get_proxy_set_type(origin=True)(instance=self, field="ledger_uids")

    def __getitem__(self, index: int | Uid | Instrument) -> Ledger:
        ledger = None

        if isinstance(index, int):
            return self.ledgers[index]

        if isinstance(index, Uid):
            entity = Entity.by_uid(index)
            if isinstance(entity, Ledger):
                if entity.uid not in self.ledger_uids:
                    msg = f"Ledger with UID {index} not found in portfolio"
                    raise KeyError(msg)
                return entity
            elif not isinstance(entity, Instrument):
                msg = f"Instrument with UID {index} not found in portfolio"
                raise KeyError(msg)
            index = entity

        if isinstance(index, Instrument):
            if (ledger := Ledger.by_instrument(index)) is None:
                msg = f"Ledger for index '{index}' not found"
                raise KeyError(msg)
            return ledger

        msg = f"Index must be an int, Uid or Instrument, got {type(index).__name__}"
        raise KeyError(msg)

    # MARK: Set ABC
    @override
    def __contains__(self, value: object) -> bool:
        if not isinstance(value, (Ledger, Uid)):
            return False
        return Ledger.narrow_to_uid(value) in self.ledger_uids

    @override
    def __iter__(self) -> Iterator[Ledger]:  # pyright: ignore[reportIncompatibleMethodOverride] since we are overriding the pydantic BaseModel iterator on purpose
        return iter(self.ledgers)

    @override
    def __len__(self) -> int:
        return len(self.ledger_uids)

    @override
    def __repr__(self) -> str:
        return super().__repr__().replace(">", f", ledgers={self.ledger_uids!r}>")
