# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING
from iso4217 import Currency

from ...journal.entity_journal import EntityJournal

from .instrument_base import InstrumentBase


class InstrumentJournal(InstrumentBase, EntityJournal, init=False):
    pass