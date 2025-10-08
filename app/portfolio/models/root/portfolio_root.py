# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING

from ..portfolio import Portfolio
from .entity_root import EntityRoot


if TYPE_CHECKING:
    from ...util.uid import Uid


class PortfolioRoot(EntityRoot[Portfolio]):
    # MARK: Portfolio
    @property
    def portfolio(self) -> Portfolio:
        return self.entity

    @portfolio.setter
    def portfolio(self, value: Uid | Portfolio) -> None:
        self.entity = value
