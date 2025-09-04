# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import dataclasses

from pydantic_core import CoreSchema, core_schema
from typing import (override, overload, Iterable,
    cast as typing_cast,
)
from enum import Enum
from collections.abc import MutableSequence, Sequence

from .collection import JournalledCollection


class JournalledSequenceEditType(Enum):
    SETITEM = "setitem"
    DELITEM = "delitem"
    INSERT  = "insert"


@dataclasses.dataclass(frozen=True, slots=True)
class JournalledSequenceEdit[T]:
    type: JournalledSequenceEditType
    index: int | slice
    value: T | Iterable[T] | None

type ImmutableSequence[T] = tuple[T,...]

class JournalledSequence[T](JournalledCollection[ImmutableSequence[T], T], MutableSequence[T]):
    # MARK: JournalledCollection ABC
    @property
    @override
    def edited(self) -> bool:
        return self._sequence is not None

    @override
    def make_immutable(self) -> ImmutableSequence[T]:
        if self._sequence is not None:
            return tuple(self._sequence)
        else:
            original = self._original
            if not isinstance(self._original, tuple):
                original = tuple(original)
            return typing_cast(ImmutableSequence[T], original)

    @override
    @classmethod
    def get_core_schema(cls, source, handler) -> CoreSchema:
        return core_schema.tuple_variable_schema(
            core_schema.is_instance_schema(
                cls.get_concrete_content_type()
            )
        )


    # MARK : Functionality
    def __init__(self, original : Sequence[T], /, **kwargs):
        super().__init__(**kwargs)
        self._original : Sequence[T] = original
        self._sequence : list[T] | None = None
        self._journal : list[JournalledSequenceEdit[T]] = []

    def _append_journal(self, type : JournalledSequenceEditType, index: int | slice, value: T | Iterable[T] | None) -> None:
        self._journal.append(JournalledSequenceEdit(type=type, index=index, value=value))
        self._on_edit()

    @property
    def original(self) -> Sequence[T]:
        return self._original

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

        self._sequence[index] = value # pyright: ignore[reportArgumentType, reportCallIssue] as the overloads are enough to ensure type safety
        self._append_journal(JournalledSequenceEditType.SETITEM, index, value)

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

        del self._sequence[index]
        self._append_journal(JournalledSequenceEditType.DELITEM, index, None)

    @override
    def insert(self, index: int, value: T) -> None:
        if self._sequence is None:
            self._copy_on_write()
        if self._sequence is None:
            raise RuntimeError("Sequence should have been copied on write")

        self._sequence.insert(index, value)
        self._append_journal(JournalledSequenceEditType.INSERT, index, value)

    @override
    def __str__(self) -> str:
        if self._sequence is None:
            return str(self._original)
        return str(self._sequence)

    @override
    def __repr__(self) -> str:
        if self._sequence is None:
            return repr(self._original)
        return repr(self._sequence)