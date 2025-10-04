# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING

from ....util.helpers.empty_class import empty_class
from ..entity import EntityRecord
from .portfolio_impl import PortfolioImpl
from .portfolio_journal import PortfolioJournal
from .portfolio_schema import PortfolioSchema


class PortfolioRecord(
    PortfolioImpl,
    PortfolioSchema if not TYPE_CHECKING else empty_class(),
    EntityRecord[PortfolioJournal],
    init=False,
    unsafe_hash=True,
):
    pass
