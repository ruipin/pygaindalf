# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import Iterator
from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, override

from ....util.helpers.empty_class import empty_class
from ...collections.ordered_view import OrderedViewSet
from ...util.uid import Uid
from ..entity import Entity, EntityImpl
from ..instrument import Instrument, InstrumentRecord
from ..ledger import Ledger, LedgerRecord
from .portfolio_schema import PortfolioSchema


class PortfolioImpl[
    T_Ledger_Set: OrderedViewSet[Ledger],
](
    EntityImpl,
    PortfolioSchema[T_Ledger_Set] if TYPE_CHECKING else empty_class(),
    AbstractSet[Ledger],
    metaclass=ABCMeta,
):
    # MARK: Ledgers
    def __getitem__(self, index: int | Uid | InstrumentRecord | Instrument) -> Ledger:
        ledger = None

        if isinstance(index, int):
            return self.ledgers[index]

        if isinstance(index, Uid):
            entity = Entity.by_uid(index)
            if isinstance(entity, Ledger):
                if entity not in self.ledgers:
                    msg = f"Ledger with UID {index} not found in portfolio"
                    raise KeyError(msg)
                return entity
            elif not isinstance(entity, Instrument):
                msg = f"Instrument with UID {index} not found in portfolio"
                raise KeyError(msg)
            index = entity

        if isinstance(index, (Instrument, InstrumentRecord)):
            instrument = Instrument.narrow_to_uid(index)
            if (ledger := Ledger.by_instrument(instrument)) is None:
                msg = f"Ledger for index '{index}' not found"
                raise KeyError(msg)
            return ledger

        msg = f"Index must be an int, Uid or InstrumentRecord, got {type(index).__name__}"
        raise KeyError(msg)

    # MARK: Set ABC
    @override
    def __contains__(self, value: object) -> bool:
        if not isinstance(value, (Ledger, LedgerRecord, Uid)):
            return False
        return Ledger.narrow_to_instance(value) in self.ledgers

    @override
    def __iter__(self) -> Iterator[Ledger]:  # pyright: ignore[reportIncompatibleMethodOverride] since we are overriding the pydantic BaseModel iterator on purpose
        return iter(self.ledgers)

    @override
    def __len__(self) -> int:
        return len(self.ledgers)

    @override
    def __repr__(self) -> str:
        return super().__repr__().replace(">", f", ledgers={self.ledgers!r}>")
