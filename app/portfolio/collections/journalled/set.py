# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import dataclasses

from pydantic_core import CoreSchema, core_schema
from typing import (override, Iterator,
    cast as typing_cast,
)
from enum import Enum
from collections.abc import MutableSet, Set

from .collection import JournalledCollection


class JournalledSetEditType(Enum):
    ADD     = "add"
    DISCARD = "discard"

@dataclasses.dataclass(frozen=True, slots=True)
class JournalledSetEdit[T]:
    type: JournalledSetEditType
    value : T

type ImmutableSet[T] = frozenset[T]

class JournalledSet[T](JournalledCollection[ImmutableSet[T], T], MutableSet[T]):
    # MARK: JournalledCollection ABC
    @property
    @override
    def edited(self) -> bool:
        return self._set is not None

    @override
    def make_immutable(self) -> ImmutableSet[T]:
        if self._set is not None:
            return frozenset(self._set)
        else:
            original = self._original
            if not isinstance(self._original, frozenset):
                original = frozenset(original)
            return typing_cast(ImmutableSet[T], original)

    @override
    @classmethod
    def get_core_schema(cls, source, handler) -> CoreSchema:
        return core_schema.frozenset_schema(
            core_schema.is_instance_schema(
                cls.get_concrete_content_type()
            )
        )

    # MARK: Functionality
    def __init__(self, original : Set[T], /, **kwargs):
        super().__init__(**kwargs)
        self._original : Set[T] = original
        self._set : set[T] | None = None
        self._journal : list[JournalledSetEdit[T]] = []

    def _append_journal(self, type : JournalledSetEditType, value : T) -> None:
        self._journal.append(JournalledSetEdit(type=type, value=value))
        self._on_edit()

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

        self._set.add(value)
        self._append_journal(JournalledSetEditType.ADD, value)

    @override
    def discard(self, value : T) -> None:
        if value not in self:
            return

        if self._set is None:
            self._copy_on_write()
        if self._set is None:
            raise RuntimeError("Set should have been copied on write")

        self._set.discard(value)
        self._append_journal(JournalledSetEditType.DISCARD, value)

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

    @override
    def __str__(self) -> str:
        if self._set is None:
            return str(self._original)
        return str(self._set)

    @override
    def __repr__(self) -> str:
        if self._set is None:
            return repr(self._original)
        return repr(self._set)