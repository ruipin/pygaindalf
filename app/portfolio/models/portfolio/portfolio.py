# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING

from ....util.helpers.empty_class import EmptyClass
from ..entity import IncrementingUidEntity
from .portfolio_base import PortfolioBase
from .portfolio_fields import PortfolioFields
from .portfolio_journal import PortfolioJournal


if TYPE_CHECKING:
    from .portfolio_proxy import PortfolioProxy  # noqa: F401


class Portfolio(
    PortfolioBase,
    PortfolioFields if not TYPE_CHECKING else EmptyClass,
    IncrementingUidEntity[PortfolioJournal, "PortfolioProxy"],
):
    pass
