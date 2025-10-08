# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import ABCMeta, abstractmethod
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

from ...util.callguard import callguard_class
from ...util.mixins import LoggableHierarchicalNamedMixin


if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from ...portfolio.journal import SessionManager
    from ...portfolio.models.portfolio import PortfolioProtocol
    from .. import Runtime


CURRENT_CONTEXT: ContextVar[BaseContext | None] = ContextVar("CURRENT_CONTEXT", default=None)


@callguard_class()
class BaseContext(LoggableHierarchicalNamedMixin, metaclass=ABCMeta):
    _parent: BaseContext | Runtime

    @staticmethod
    def get_current_context() -> BaseContext | None:
        return CURRENT_CONTEXT.get()

    def __init__(self, parent: BaseContext | Runtime) -> None:
        self._parent = parent

    @property
    def _runtime(self) -> Runtime:
        from .. import Runtime

        parent = self._parent
        if isinstance(parent, Runtime):
            return parent
        return parent._runtime  # noqa: SLF001

    @property
    @abstractmethod
    def portfolio(self) -> PortfolioProtocol:
        msg = "Subclasses must implement the 'portfolio' property."
        raise NotImplementedError(msg)

    @property
    def session_manager(self) -> SessionManager:
        return self.portfolio.session_manager

    def __call__(self) -> AbstractContextManager[Token]:
        return CURRENT_CONTEXT.set(self)
