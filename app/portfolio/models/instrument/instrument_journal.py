# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from ...journal.entity_journal import EntityJournal
from .instrument_base import InstrumentBase


class InstrumentJournal(InstrumentBase, EntityJournal, init=False):
    pass
