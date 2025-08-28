# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import ConfigDict, Field, PrivateAttr, computed_field
from contextlib import contextmanager
from typing import Iterator, TypedDict, Unpack

from ...util.mixins import LoggableHierarchicalModel
from ...util.helpers.callguard import callguard_class

from .session import Session


class SessionParams(TypedDict, total=False):
    actor  : str
    reason : str


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

    @contextmanager
    def __call__(self, **kwargs : Unpack[SessionParams]) -> Iterator[Session]:
        try:
            self._start(**kwargs)
            if self._session is None:
                raise RuntimeError("Session failed to start.")

            yield self._session

            if self._session is None:
                raise RuntimeError("Session is no longer valid.")

            self._session.commit()
        except Exception as e:
            if self._session is not None:
                self._session.abort()
            raise e
        finally:
            self._end()


    # MARK: Active
    @computed_field(description="Indicates if there is a currently active session.")
    @property
    def in_session(self) -> bool:
        return self._session is not None

    @property
    def session(self) -> Session | None:
        return self._session