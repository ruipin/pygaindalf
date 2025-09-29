# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, override

from ..portfolio import Portfolio
from .entity_root import EntityRoot


if TYPE_CHECKING:
    from ...util.uid import Uid


class PortfolioRoot(EntityRoot):
    # MARK: Portfolio
    @property
    def portfolio_uid(self) -> Uid:
        if (uid := self.root_uid) is None:
            msg = "Root UID is None"
            raise ValueError(msg)
        if uid.namespace != Portfolio.uid_namespace():
            msg = "Root UID is not a Portfolio UID"
            raise ValueError(msg)
        return uid

    @portfolio_uid.setter
    def portfolio_uid(self, value: Uid | Portfolio) -> None:
        self.root_uid = Portfolio.narrow_to_uid(value)

    @property
    def portfolio(self) -> Portfolio:
        if not isinstance((root := self.root), Portfolio):
            msg = "Root is not a Portfolio"
            raise TypeError(msg)
        return root

    @portfolio.setter
    def portfolio(self, value: Portfolio | Uid) -> None:
        self.root_uid = Portfolio.narrow_to_uid(value)

    @override
    @classmethod
    def _do_validate_root_uid(cls, root_uid: Uid) -> None:
        super()._do_validate_root_uid(root_uid)

        if root_uid.namespace != Portfolio.uid_namespace():
            msg = f"Root UID namespace '{root_uid.namespace}' does not match expected namespace '{Portfolio.uid_namespace}'."
            raise ValueError(msg)
