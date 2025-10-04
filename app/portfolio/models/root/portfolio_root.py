# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, override

from ..portfolio import Portfolio, PortfolioRecord
from .entity_root import EntityRoot


if TYPE_CHECKING:
    from ...util.uid import Uid
    from ..entity import Entity


class PortfolioRoot(EntityRoot):
    # MARK: PortfolioRecord
    @property
    def portfolio(self) -> Portfolio:
        if not isinstance((root := self.root), Portfolio):
            msg = f"Expected root to be a Portfolio, got {type(root).__name__}"
            raise TypeError(msg)
        return root

    @portfolio.setter
    def portfolio(self, value: Uid | Portfolio | PortfolioRecord) -> None:
        self.root = Portfolio.narrow_to_instance(value)

    @override
    @classmethod
    def _do_validate_root(cls, root: Entity) -> None:
        super()._do_validate_root(root)

        if not isinstance(root, Portfolio):
            msg = f"Expected root to be a Portfolio, got {type(root).__name__}"
            raise TypeError(msg)
