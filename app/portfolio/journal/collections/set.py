# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import dataclasses

from typing import override, Iterator
from enum import Enum
from collections.abc import MutableSet, Set


class JournalledSetEditType(Enum):
    ADD     = "add"
    DISCARD = "discard"

@dataclasses.dataclass(frozen=True, slots=True)
class JournalledSetEdit[T]:
    type: JournalledSetEditType
    value : T


class JournalledSet[T](MutableSet[T]):
    def __init__(self, original : Set[T]):
        self._original : Set[T] = original
        self._set : set[T] | None = None
        self._journal : list[JournalledSetEdit[T]] = []

    def _append_journal(self, type : JournalledSetEditType, value : T) -> None:
        self._journal.append(JournalledSetEdit(type=type, value=value))

    @property
    def edited(self) -> bool:
        return self._set is not None

    def _copy_on_write(self) -> None:
        if self._set is not None:
            raise RuntimeError("Set is already modified")
        self._set = set(self._original)

    @override
    def __contains__(self, value : object) -> bool:
        if self._set is None:
            return value in self._original
        return value in self._set

    @override
    def add(self, value : T) -> None:
        if value in self:
            return

        if self._set is None:
            self._copy_on_write()
        if self._set is None:
            raise RuntimeError("Set should have been copied on write")

        self._append_journal(JournalledSetEditType.ADD, value)
        self._set.add(value)

    @override
    def discard(self, value : T) -> None:
        if value not in self:
            return

        if self._set is None:
            self._copy_on_write()
        if self._set is None:
            raise RuntimeError("Set should have been copied on write")

        self._append_journal(JournalledSetEditType.DISCARD, value)
        self._set.discard(value)

    @override
    def __iter__(self) -> Iterator[T]:
        if self._set is None:
            return iter(self._original)
        else:
            return iter(self._set)

    @override
    def __len__(self):
        if self._set is None:
            return len(self._original)
        else:
            return len(self._set)