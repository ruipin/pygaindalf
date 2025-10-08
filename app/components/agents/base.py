# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from typing import TYPE_CHECKING, override

from ...util.helpers import classproperty
from ..component import BaseComponent, BaseComponentConfig, component_entrypoint


if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from ...portfolio.journal import Session
    from ...portfolio.models.portfolio import PortfolioProtocol
    from ...runtime.context import BaseContext


# MARK: Agent Base Configuration
class BaseAgentConfig(BaseComponentConfig, metaclass=ABCMeta):
    @classproperty
    @override
    def package_root(cls) -> str:
        return "app.components.agents"


# MARK: Agent Base class
class BaseAgent[C: BaseAgentConfig](BaseComponent[C], metaclass=ABCMeta):
    context: BaseContext

    @component_entrypoint
    def run(self, context: BaseContext) -> None:
        self.context = context

        self._pre_run()
        self._do_run()
        self._post_run()

    def session(self, reason: str) -> AbstractContextManager[Session]:
        return self.context.session_manager(actor=self.instance_hierarchy, reason=reason)

    def s(self, reason: str) -> AbstractContextManager[Session]:
        return self.session(reason=reason)

    @property
    def portfolio(self) -> PortfolioProtocol:
        return self.context.portfolio

    def _pre_run(self) -> None:
        pass

    def _do_run(self) -> None:
        msg = f"{type(self).__name__} must implement the _do_run method."
        raise NotImplementedError(msg)

    def _post_run(self) -> None:
        pass
