# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import dataclasses

from collections.abc import Iterable, MutableSequence, Sequence
from enum import Enum
from typing import (
    overload,
    override,
)

from pydantic_core import CoreSchema, core_schema

from ....util.models.uid import Uid, UidProtocol
from .collection import JournalledCollection


class JournalledSequenceEditType(Enum):
    SETITEM = "setitem"
    DELITEM = "delitem"
    INSERT = "insert"


@dataclasses.dataclass(frozen=True, slots=True)
class JournalledSequenceEdit[T]:
    type: JournalledSequenceEditType
    index: int | slice
    value: T | Uid | Iterable[T | Uid] | None

    @override
    def __str__(self) -> str:
        return f"{self.type.value}({self.index}: {self.value})"

    @override
    def __repr__(self) -> str:
        return self.__str__()


class JournalledSequence[T](JournalledCollection[T, Sequence[T], list[T], tuple[T, ...], JournalledSequenceEdit[T]], MutableSequence[T]):
    # MARK: JournalledCollection ABC
    @override
    @classmethod
    def get_core_schema(cls, source, handler) -> CoreSchema:  # noqa: ANN001
        return core_schema.tuple_variable_schema(core_schema.is_instance_schema(cls.get_concrete_value_type(source)))

    # MARK : Functionality
    def _append_journal(self, type: JournalledSequenceEditType, index: int | slice, value: T | Iterable[T] | None) -> None:  # NOQA: A002
        if isinstance(value, Iterable):
            _value = tuple(v.uid if isinstance(v, UidProtocol) else v for v in value)
        else:
            _value = value.uid if isinstance(value, UidProtocol) else value

        self._journal.append(JournalledSequenceEdit(type=type, index=index, value=_value))
        self._on_edit()

    @overload
    def __getitem__(self, index: int) -> T: ...
    @overload
    def __getitem__(self, index: slice) -> MutableSequence[T]: ...
    @override
    def __getitem__(self, index: int | slice) -> T | MutableSequence[T]:
        if isinstance(index, slice):
            msg = "Sliced read access not implemented yet"
            raise NotImplementedError(msg)

        return self._get_container()[index]

    @overload
    def __setitem__(self, index: int, value: T) -> None: ...
    @overload
    def __setitem__(self, index: slice, value: Iterable[T]) -> None: ...
    @override
    def __setitem__(self, index: int | slice, value: T | Iterable[T]) -> None:
        self._get_mut_container()[index] = value  # pyright: ignore[reportArgumentType, reportCallIssue] as the overloads are enough to ensure type safety
        self._append_journal(JournalledSequenceEditType.SETITEM, index, value)

    @overload
    def __delitem__(self, index: int) -> None: ...
    @overload
    def __delitem__(self, index: slice) -> None: ...
    @override
    def __delitem__(self, index: int | slice) -> None:
        del self._get_mut_container()[index]
        self._append_journal(JournalledSequenceEditType.DELITEM, index, None)

    @override
    def insert(self, index: int, value: T) -> None:
        self._get_mut_container().insert(index, value)
        self._append_journal(JournalledSequenceEditType.INSERT, index, value)
