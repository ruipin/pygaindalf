# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, Protocol, runtime_checkable, Literal

if TYPE_CHECKING:
    from .session import Session


@runtime_checkable
class SessionManagerHooksProtocol(Protocol):
    def on_session_start     (self, session: Session) -> None: ...
    def on_session_end       (self, session: Session) -> None: ...
    def on_session_invalidate(self, session: Session) -> None: ...
    def on_session_apply     (self, session: Session) -> None: ...
    def on_session_commit    (self, session: Session) -> None: ...
    def on_session_abort     (self, session: Session) -> None: ...

type SessionManagerHookLiteral = (
    Literal['start'     ] |
    Literal['end'       ] |
    Literal['invalidate'] |
    Literal['apply'     ] |
    Literal['commit'    ] |
    Literal['abort'     ]
)