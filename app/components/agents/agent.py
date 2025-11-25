# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from typing import TYPE_CHECKING, override

from ...context import ContextConfig
from ...util.config import FieldInherit
from ...util.helpers import classproperty
from ..component import Component, ComponentConfig, component_entrypoint


if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from ...context import Context
    from ...portfolio.journal import Session


# MARK: Agent Base Configuration
class AgentConfig(ComponentConfig, metaclass=ABCMeta):
    context: ContextConfig = FieldInherit(default_factory=lambda: ContextConfig(), description="Context configuration for provider")

    @classproperty
    @override
    def package_root(cls) -> str:
        return "app.components.agents"


# MARK: Agent Base class
class Agent[C: AgentConfig](Component[C], metaclass=ABCMeta):
    # MARK: Run
    @component_entrypoint
    def run(self, context: Context) -> None:
        assert self.context is context, "The provided context does not match the current configured context."
        self.__dict__["context"] = context  # cache context, replacing base property

        self._pre_run()
        self._do_run()
        self._post_run()

    def _pre_run(self) -> None:
        self.log.info(t"Running {self.instance_hierarchy}...")

    def _do_run(self) -> None:
        msg = f"{type(self).__name__} must implement the _do_run method."
        raise NotImplementedError(msg)

    def _post_run(self) -> None:
        self.log.info(t"{self.instance_hierarchy} finished running.")

    # MARK: Session Manager
    def session(self, reason: str) -> AbstractContextManager[Session]:
        return self.context.session_manager(actor=self.instance_hierarchy, reason=reason)

    def s(self, reason: str) -> AbstractContextManager[Session]:
        return self.session(reason=reason)
