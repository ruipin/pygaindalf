# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING

from ....util.helpers.empty_class import empty_class
from ..entity import Entity, IncrementingUidMixin
from .portfolio_impl import PortfolioImpl
from .portfolio_journal import PortfolioJournal
from .portfolio_record import PortfolioRecord


class Portfolio(
    PortfolioImpl if TYPE_CHECKING else empty_class(),
    IncrementingUidMixin,
    Entity[PortfolioRecord, PortfolioJournal],
    init=False,
):
    pass


PortfolioRecord.register_entity_class(Portfolio)
