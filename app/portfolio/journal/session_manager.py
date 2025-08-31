# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import contextlib

from pydantic import ConfigDict, PrivateAttr, computed_field
from typing import Iterator, TypedDict, Unpack

from ...util.mixins import LoggableHierarchicalModel
from ...util.helpers.callguard import callguard_class

from .session import Session, SessionParams


@callguard_class()
class SessionManager(LoggableHierarchicalModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=False,
        validate_assignment=True,
    )

    _session : Session | None = PrivateAttr(default=None)


    # MARK: Session
    def _start(self, **kwargs : Unpack[SessionParams]) -> Session:
        if self.in_session:
            raise RuntimeError("A session is already active.")

        session = self._session = Session(instance_parent=self, **kwargs)
        return session

    def _commit(self) -> None:
        raise NotImplementedError("Journal commit not implemented yet.")

    def _abort(self) -> None:
        raise NotImplementedError("Journal abort not implemented yet.")

    def _end(self) -> None:
        self._session = None

    @contextlib.contextmanager
    def __call__(self, **kwargs : Unpack[SessionParams]) -> Iterator[Session]:
        session = self._start(**kwargs)
        try:
            if self._session is not session:
                raise RuntimeError("Session failed to start.")

            yield session

            if self._session is not session:
                raise RuntimeError("Session is no longer valid.")

            if not session.ended:
                session.commit()
        except Exception as e:
            if self._session is not session:
                raise RuntimeError("Session is no longer valid.")

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
        return self._session is not None

    @property
    def session(self) -> Session | None:
        return self._session