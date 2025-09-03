# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override, Annotated, overload, Literal, Any, TYPE_CHECKING
from pydantic import Field, PrivateAttr, field_validator
from functools import cached_property
from collections.abc import MutableMapping, Mapping

from ..components.providers.provider import ProviderBase
from ..util.helpers.frozendict import frozendict, FrozenDict

from .models.ledger import Ledger
from .models.instrument import Instrument
from .models.uid import Uid

from .models.entity import IncrementingUidEntity

from .journal.session_manager import SessionManager
from .journal.collections import JournalledMapping


class Portfolio(IncrementingUidEntity):
    # MARK: Ledgers
    # Make type checkers believe that the ledgers set is mutable
    if TYPE_CHECKING:
        ledgers_ : FrozenDict[Uid, Ledger] = Field(default_factory=lambda: frozendict[Uid, Ledger](), alias='ledgers')
        @property
        def ledgers(self) -> MutableMapping[Uid,Ledger]: ...
        @ledgers.setter
        def ledgers(self, value : MutableMapping[Uid,Ledger] | Mapping[Uid,Ledger]) -> None: ...
    else:
        ledgers : FrozenDict[Uid, Ledger] = Field(default_factory=lambda: frozendict[Uid, Ledger](), description="A mapping of Instrument UIDs to Ledger instances.")

    @field_validator('ledgers', mode='after')
    def _validate_ledgers(cls, v : FrozenDict[Uid, Ledger]) -> FrozenDict[Uid, Ledger]:
        # Ensure all UIDs have the Ledger Namespace
        for uid in v.keys():
            if uid.namespace != Ledger.uid_namespace():
                raise ValueError(f"All keys in 'ledgers' must be UIDs with the '{Ledger.uid_namespace()}' namespace. Found key with namespace '{uid.namespace}'.")
        return v


    # MARK: Utilities
    @override
    def __repr__(self) -> str:
        return f"Portfolio(ledgers={', '.join(str(v) for v in self.ledgers.values())})"