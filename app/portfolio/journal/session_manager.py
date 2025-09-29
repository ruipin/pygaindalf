# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import contextlib
import weakref

from collections.abc import Iterator
from typing import Any, Protocol, Unpack, runtime_checkable

from pydantic import ConfigDict, PrivateAttr, computed_field, field_validator

from ...util.models import LoggableHierarchicalModel
from .protocols import SessionManagerHookLiteral, SessionManagerHooksProtocol
from .session import Session, SessionParams


class SessionManager(LoggableHierarchicalModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        validate_assignment=True,
    )

    _session: Session | None = PrivateAttr(default=None)

    # MARK: Global instance behaviour
    @staticmethod
    def get_global_manager_or_none() -> SessionManager | None:
        from ..models.root import EntityRoot

        if (global_root := EntityRoot.get_global_root_or_none()) is None:
            return None
        return global_root.session_manager

    @staticmethod
    def get_global_manager() -> SessionManager:
        from ..models.root import EntityRoot

        return EntityRoot.get_global_root().session_manager

    # MARK: Instance Parent
    @field_validator("instance_parent_weakref", mode="before")
    def _validate_instance_parent_is_session_manager(cls, v: Any) -> Any:
        from ..models.entity.entity import Entity

        obj = v() if isinstance(v, weakref.ref) else v
        if obj is None or not isinstance(obj, Entity):
            msg = "Session parent must be a Entity object"
            raise TypeError(msg)
        return v

    def _get_owner(self) -> SessionManagerHooksProtocol | None:
        if not isinstance((parent := self.instance_parent), SessionManagerHooksProtocol):
            return None
        return parent

    def call_owner_hook(self, hook_name: SessionManagerHookLiteral, *args: Any, **kwargs: Any) -> None:
        if (owner := self._get_owner()) is not None:
            getattr(owner, f"on_session_{hook_name}")(*args, **kwargs)

    # MARK: Session
    def _start(self, **kwargs: Unpack[SessionParams]) -> Session:
        if self.in_session:
            msg = "A session is already active."
            raise RuntimeError(msg)

        session = self._session = Session(instance_parent=weakref.ref(self), **kwargs)
        return session

    def _commit(self) -> None:
        session = self._session
        if session is None or session.ended:
            return
        session.commit()

    def _abort(self) -> None:
        session = self._session
        if session is None or session.ended:
            return
        session.abort()

    def _end(self) -> None:
        self._session = None

    @contextlib.contextmanager
    def __call__(self, *, reuse: bool = False, **kwargs: Unpack[SessionParams]) -> Iterator[Session]:
        if reuse and (session := self._session) is not None and not session.ended:
            yield session
            return

        session = self._start(**kwargs)
        try:
            if self._session is not session:
                msg = "Session failed to start."
                raise RuntimeError(msg)  # noqa: TRY301

            yield session

            if self._session is not session:
                msg = "Session is no longer valid."
                raise RuntimeError(msg)  # noqa: TRY301

            self._commit()
        except Exception as err:
            if self._session is not session:
                msg = "Session is no longer valid."
                raise RuntimeError(msg) from err

            self._abort()

            raise
        finally:
            if not session.ended:
                self._end()

    # MARK: Active
    @computed_field(description="Indicates if there is a currently active session.")
    @property
    def in_session(self) -> bool:
        return self._session is not None and not self._session.ended

    @property
    def session(self) -> Session | None:
        return self._session if self.in_session else None


@runtime_checkable
class HasSessionManagerProtocol(Protocol):
    @property
    def session_manager(self) -> SessionManager: ...
