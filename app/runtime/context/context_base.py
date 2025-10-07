# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from ...util.callguard import callguard_class
from ...util.mixins import LoggableHierarchicalNamedMixin


if TYPE_CHECKING:
    from ...portfolio.models.portfolio import PortfolioProtocol
    from ...runtime import Runtime


@callguard_class()
class BaseContext(LoggableHierarchicalNamedMixin, metaclass=ABCMeta):
    _parent: BaseContext | Runtime

    def __init__(self, parent: BaseContext | Runtime) -> None:
        self._parent = parent

    @property
    def _runtime(self) -> Runtime:
        from ...runtime import Runtime

        parent = self._parent
        if isinstance(parent, Runtime):
            return parent
        return parent._runtime  # noqa: SLF001

    @property
    @abstractmethod
    def portfolio(self) -> PortfolioProtocol:
        msg = "Subclasses must implement the 'portfolio' property."
        raise NotImplementedError(msg)
