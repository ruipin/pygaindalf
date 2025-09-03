# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .session import JournalSession
    from ..models.entity import Entity

@runtime_checkable
class SessionManagerOwnerProtocol(Protocol):
    def on_session_start(self, session: 'JournalSession') -> None: ...
    def on_session_end(self, session: 'JournalSession') -> None: ...
    def on_session_commit(self, session: 'JournalSession') -> None: ...
    def on_session_abort(self, session: 'JournalSession') -> None: ...