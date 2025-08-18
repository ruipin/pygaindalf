# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from pydantic import Field

from ..components.providers.provider import ProviderBase
from ..util.helpers.frozendict import frozendict, FrozenDict

from .models.ledger import Ledger
from .models.instrument import Instrument

from .models import IncrementingUidEntity


class Portfolio(IncrementingUidEntity):
    ledgers  : FrozenDict[Instrument, Ledger] = Field(default_factory=lambda: frozendict[Instrument, Ledger](), description="A mapping of ledger IDs to Ledger instances.")
    providers: FrozenDict[str, ProviderBase ] = Field(default_factory=lambda: frozendict[str, ProviderBase ](), description="A mapping of provider IDs to provider instances.")

#    def get_ledger(self, security_id: str) -> Ledger | None: ...
#    def add_transaction(self, tx: Transaction): ...
#    def replace_transaction(self, old_tx_id: str, new_tx: Transaction): ...
#    def log_audit(self, event: 'AuditEvent'): ...
#    def view_builder(self) -> 'ViewBuilder': ...