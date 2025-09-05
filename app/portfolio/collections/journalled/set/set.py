# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Set

from .generic_set import GenericJournalledSet


class JournalledSet[T](GenericJournalledSet[T, Set[T], set[T], frozenset[T]]):
    pass