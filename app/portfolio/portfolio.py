# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override
from pydantic import Field, PrivateAttr
from functools import cached_property

from ..components.providers.provider import ProviderBase
from ..util.helpers.frozendict import frozendict, FrozenDict

from .models.ledger import Ledger
from .models.instrument import Instrument
from .models.uid import Uid

from .models import IncrementingUidEntity

from .journal.session_manager import SessionManager


class Portfolio(IncrementingUidEntity):
    #providers : FrozenDict[str, ProviderBase] = Field(default_factory=lambda: frozendict[str, ProviderBase](), description="A mapping of provider IDs to provider instances.")

    ledgers : FrozenDict[Uid, Ledger] = Field(default_factory=lambda: frozendict[Uid, Ledger](), description="A mapping of Instrument UIDs to Ledger instances.")

#    def get_ledger(self, security_id: str) -> Ledger | None: ...
#    def add_transaction(self, tx: Transaction): ...
#    def replace_transaction(self, old_tx_id: str, new_tx: Transaction): ...
#    def log_audit(self, event: 'AuditEvent'): ...
#    def view_builder(self) -> 'ViewBuilder': ...


    # MARK: Journal
    _session_manager : SessionManager = PrivateAttr(default_factory=SessionManager)

    @cached_property
    @override
    def session_manager(self) -> SessionManager:
        return self._session_manager