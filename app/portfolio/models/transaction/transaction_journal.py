# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from ...journal.entity_journal import EntityJournal
from .transaction_base import TransactionBase


class TransactionJournal(TransactionBase, EntityJournal, init=False):
    pass