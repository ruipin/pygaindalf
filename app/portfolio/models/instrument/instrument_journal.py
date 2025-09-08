# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING
from iso4217 import Currency

from ...journal.entity_journal import EntityJournal


class InstrumentJournal(EntityJournal, init=False):
    # Help the type checker understand the structure of the proxied object
    if TYPE_CHECKING:
        isin     : str | None
        ticker   : str | None
        currency : Currency