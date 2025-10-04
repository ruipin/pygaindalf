# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from ...journal.journal import Journal
from .instrument_impl import InstrumentImpl


class InstrumentJournal(
    InstrumentImpl,
    Journal,
    init=False,
):
    pass
