# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from ..entity import EntityRecord
from .portfolio_impl import PortfolioImpl
from .portfolio_journal import PortfolioJournal
from .portfolio_schema import PortfolioSchema


class PortfolioRecord(
    PortfolioImpl,
    EntityRecord[PortfolioJournal],
    PortfolioSchema,
    init=False,
    unsafe_hash=True,
):
    pass
