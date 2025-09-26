# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING
from pydantic import Field
from functools import cached_property
from collections.abc import Set

from ....util.helpers.empty_class import EmptyClass

from ..entity import IncrementingUidEntity
from ..uid import Uid
from ..ledger import UidProxyOrderedViewLedgerFrozenSet, OrderedViewFrozenLedgerUidSet

from .portfolio_fields import PortfolioFields
from .portfolio_base import PortfolioBase
from .portfolio_journal import PortfolioJournal


class Portfolio(
    PortfolioBase,
    PortfolioFields if not TYPE_CHECKING else EmptyClass,
    IncrementingUidEntity[PortfolioJournal]
):
    pass