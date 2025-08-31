# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import dataclasses

from typing import override, overload, Iterable
from enum import Enum
from collections.abc import MutableSequence, Sequence


class JournalledSequenceEditType(Enum):
    SETITEM = "setitem"
    DELITEM = "delitem"
    INSERT  = "insert"


@dataclasses.dataclass(frozen=True, slots=True)
class JournalledSequenceEdit[T]:
    type: JournalledSequenceEditType
    index: int | slice
    value: T | Iterable[T] | None


class JournalledSequence[T](MutableSequence[T]):
    def __init__(self, original : Sequence[T]):
        self._original : Sequence[T] = original
        self._sequence : list[T] | None = None
        self._journal : list[JournalledSequenceEdit[T]] = []

    def _append_journal(self, type : JournalledSequenceEditType, index: int | slice, value: T | Iterable[T] | None) -> None:
        self._journal.append(JournalledSequenceEdit(type=type, index=index, value=value))

    @property
    def edited(self) -> bool:
        return self._sequence is not None

    def _copy_on_write(self) -> None:
        if self._sequence is not None:
            raise RuntimeError("Sequence is already modified")
        self._sequence = list(self._original)

    @override
    def __len__(self) -> int:
        if self._sequence is None:
            return len(self._original)
        else:
            return len(self._sequence)

    @overload
    def __getitem__(self, index: int) -> T: ...
    @overload
    def __getitem__(self, index: slice) -> MutableSequence[T]: ...
    @override
    def __getitem__(self, index: int | slice) -> T | MutableSequence[T]:
        if isinstance(index, slice):
            raise NotImplementedError("Sliced read access not implemented yet")

        if self._sequence is None and not isinstance(index, slice):
            return self._original[index]
        elif self._sequence is None:
            self._copy_on_write()
        if self._sequence is None:
            raise RuntimeError("Sequence should have been copied on write")

        return self._sequence[index]

    @overload
    def __setitem__(self, index: int, value: T) -> None: ...
    @overload
    def __setitem__(self, index: slice, value: Iterable[T]) -> None: ...
    @override
    def __setitem__(self, index: int | slice, value: T | Iterable[T]) -> None:
        if self._sequence is None:
            self._copy_on_write()
        if self._sequence is None:
            raise RuntimeError("Sequence should have been copied on write")

        self._append_journal(JournalledSequenceEditType.SETITEM, index, value)
        self._sequence[index] = value # pyright: ignore[reportArgumentType, reportCallIssue] as the overloads are enough to ensure type safety

    @overload
    def __delitem__(self, index: int) -> None: ...
    @overload
    def __delitem__(self, index: slice) -> None: ...
    @override
    def __delitem__(self, index: int | slice) -> None:
        if self._sequence is None:
            self._copy_on_write()
        if self._sequence is None:
            raise RuntimeError("Sequence should have been copied on write")

        self._append_journal(JournalledSequenceEditType.DELITEM, index, None)
        del self._sequence[index]

    @override
    def insert(self, index: int, value: T) -> None:
        if self._sequence is None:
            self._copy_on_write()
        if self._sequence is None:
            raise RuntimeError("Sequence should have been copied on write")

        self._append_journal(JournalledSequenceEditType.INSERT, index, value)
        self._sequence.insert(index, value)