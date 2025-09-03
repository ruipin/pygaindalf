# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import contextlib
import weakref

from pydantic import ConfigDict, PrivateAttr, computed_field, field_validator
from typing import Iterator, TypedDict, Unpack, Any, Protocol, runtime_checkable, Literal

from ...util.mixins import LoggableHierarchicalModel

from .session import JournalSession, SessionParams
from .owner_protocol import SessionManagerOwnerProtocol


class SessionManager(LoggableHierarchicalModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=False,
        validate_assignment=True,
    )

    _session : JournalSession | None = PrivateAttr(default=None)


    # MARK: Instance Parent
    @field_validator('instance_parent_weakref', mode='before')
    def _validate_instance_parent_is_session_manager(cls, v: Any) -> Any:
        from ..models.entity.entity import Entity
        obj = v() if isinstance(v, weakref.ref) else v
        if obj is None or not isinstance(obj, Entity):
            raise TypeError("Session parent must be a Entity object")
        return v

    def _get_owner(self) -> SessionManagerOwnerProtocol | None:
        if not isinstance((parent := self.instance_parent), SessionManagerOwnerProtocol):
            return None
        return parent

    def call_owner_hook(self, hook_name: Literal['start'] | Literal['end'] | Literal['commit'] | Literal['abort'], *args: Any, **kwargs: Any) -> None:
        if (owner := self._get_owner()) is not None:
            getattr(owner, f"on_session_{hook_name}")(*args, **kwargs)


    # MARK: JournalSession
    def _start(self, **kwargs : Unpack[SessionParams]) -> JournalSession:
        if self.in_session:
            raise RuntimeError("A session is already active.")

        session = self._session = JournalSession(instance_parent=weakref.ref(self), **kwargs)
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
    def __call__(self, **kwargs : Unpack[SessionParams]) -> Iterator[JournalSession]:
        session = self._start(**kwargs)
        try:
            if self._session is not session:
                raise RuntimeError("JournalSession failed to start.")

            yield session

            if self._session is not session:
                raise RuntimeError("JournalSession is no longer valid.")

            self._commit()
        except Exception as e:
            if self._session is not session:
                raise RuntimeError("JournalSession is no longer valid.")

            self._abort()

            raise e
        finally:
            if not session.ended:
                self._end()


    # MARK: Active
    @computed_field(description="Indicates if there is a currently active session.")
    @property
    def in_session(self) -> bool:
        return self._session is not None and not self._session.ended

    @property
    def session(self) -> JournalSession | None:
        return self._session if self.in_session else None



@runtime_checkable
class HasSessionManagerProtocol(Protocol):
    @property
    def session_manager(self) -> SessionManager: ...