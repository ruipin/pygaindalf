# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Set as AbstractSet

from .generic_set import GenericJournalledSet


class JournalledSet[T](GenericJournalledSet[T, AbstractSet[T], set[T], frozenset[T]]):
    pass
