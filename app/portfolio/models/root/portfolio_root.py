# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from pydantic import field_validator
from typing import Any, override

from ...util.uid import Uid
from ..portfolio import Portfolio

from .entity_root import EntityRoot


class PortfolioRoot(EntityRoot):
    # MARK: Portfolio
    @property
    def portfolio_uid(self) -> Uid:
        if (uid := self.root_uid) is None:
            raise ValueError("Root UID is None")
        if uid.namespace != Portfolio.uid_namespace():
            raise ValueError("Root UID is not a Portfolio UID")
        return uid

    @portfolio_uid.setter
    def portfolio_uid(self, value: Uid | Portfolio) -> None:
        self.root_uid = Portfolio.narrow_to_uid(value)

    @property
    def portfolio(self) -> Portfolio:
        if not isinstance((root := self.root), Portfolio):
            raise TypeError("Root is not a Portfolio")
        return root

    @portfolio.setter
    def portfolio(self, value: Portfolio | Uid) -> None:
        self.root_uid = Portfolio.narrow_to_uid(value)


    @override
    @classmethod
    def _do_validate_root_uid(cls, root_uid : Uid) -> None:
        super()._do_validate_root_uid(root_uid)

        if root_uid.namespace != Portfolio.uid_namespace():
            raise ValueError(f"Root UID namespace '{root_uid.namespace}' does not match expected namespace '{Portfolio.uid_namespace}'.")