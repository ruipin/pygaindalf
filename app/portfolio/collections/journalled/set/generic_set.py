# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import dataclasses

from pydantic_core import CoreSchema, core_schema
from typing import (override, Iterator, Any, Self,
    cast as typing_cast,
)
from enum import Enum
from collections.abc import MutableSet, Set, Collection

from .....util.helpers import generics

from ..collection import JournalledCollection


class JournalledSetEditType(Enum):
    ADD          = "add"
    DISCARD      = "discard"
    ITEM_UPDATED = "item_updated"  # Used when an item in the set has been updated (e.g., an entity that is part of the set has been modified)

@dataclasses.dataclass(frozen=True, slots=True)
class JournalledSetEdit[T]:
    type: JournalledSetEditType
    value : T



class GenericJournalledSet[T : Any, T_Original : Set, T_Mutable : MutableSet, T_Immutable : Set](JournalledCollection[T, T_Original, T_Mutable, T_Immutable, JournalledSetEdit], MutableSet[T]):
    # MARK: Functionality
    def _append_journal(self, type : JournalledSetEditType, value : T) -> None:
        self._journal.append(JournalledSetEdit(type=type, value=value))
        self._on_edit()

    @override
    def __contains__(self, value : object) -> bool:
        return value in self._get_container()

    @override
    def add(self, value : T) -> None:
        if value in self:
            return

        self._get_mut_container().add(value)
        self._append_journal(JournalledSetEditType.ADD, value)

    @override
    def discard(self, value : T) -> None:
        if value not in self:
            return

        self._get_mut_container().discard(value)
        self._append_journal(JournalledSetEditType.DISCARD, value)

    @override
    def __iter__(self) -> Iterator[T]:
        return iter(self._get_container())


    # MARK: Pydantic
    @override
    @classmethod
    def get_core_schema(cls, source, handler) -> CoreSchema:
        return core_schema.frozenset_schema(
            core_schema.is_instance_schema(
                cls.get_concrete_value_type(source)
            )
        )