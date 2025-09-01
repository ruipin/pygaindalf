# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import contextlib

from pydantic import ConfigDict, PrivateAttr, computed_field, field_validator
from typing import Iterator, TypedDict, Unpack, Any, Protocol, runtime_checkable

from ...util.mixins import LoggableHierarchicalModel

from .session import JournalSession, SessionParams
from . import RefreshableEntitiesProtocol


class SessionManager(LoggableHierarchicalModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=False,
        validate_assignment=True,
    )

    _session : JournalSession | None = PrivateAttr(default=None)


    # MARK: Instance Parent
    @field_validator('instance_parent', mode='before')
    def _validate_instance_parent_is_session_manager(cls, v: Any) -> Any:
        from ..models.entity.entity import Entity
        if v is None or not isinstance(v, Entity):
            raise TypeError("Session parent must be a Entity object")
        return v

    def refresh_entities(self) -> None:
        parent = self.instance_parent

        from ..models.entity.entity import Entity
        if isinstance(parent, RefreshableEntitiesProtocol):
            parent.refresh_entities()
        elif isinstance(parent, Entity):
            if not parent.superseded:
                return
            self.instance_parent = parent.superseding

    # MARK: JournalSession
    def _start(self, **kwargs : Unpack[SessionParams]) -> JournalSession:
        if self.in_session:
            raise RuntimeError("A session is already active.")

        session = self._session = JournalSession(instance_parent=self, **kwargs)
        return session

    def _commit(self) -> None:
        raise NotImplementedError("Journal commit not implemented yet.")

    def _abort(self) -> None:
        raise NotImplementedError("Journal abort not implemented yet.")

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

            if not session.ended:
                session.commit()
        except Exception as e:
            if self._session is not session:
                raise RuntimeError("JournalSession is no longer valid.")

            if not session.ended:
                session.abort()

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