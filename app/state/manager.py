# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from ..components.providers.provider import ProviderBase


#class StateManager:
#    ledgers: dict[str, Ledger]
#    providers: dict[str, ProviderBase]
#    #audit_log: list[AuditEvent]
#
#    def get_ledger(self, security_id: str) -> Ledger | None: ...
#    def add_transaction(self, tx: Transaction): ...
#    def replace_transaction(self, old_tx_id: str, new_tx: Transaction): ...
#    def log_audit(self, event: 'AuditEvent'): ...
#    def view_builder(self) -> 'ViewBuilder': ...