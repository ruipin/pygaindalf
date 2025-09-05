# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import dataclasses

from pydantic_core import CoreSchema
from typing import (override, Iterator,
    cast as typing_cast,
)
from enum import Enum
from collections.abc import MutableMapping, Mapping

from ....util.helpers.frozendict import frozendict, PydanticFrozenDictAnnotation

from .collection import JournalledCollection


class JournalledMappingEditType(Enum):
    SETITEM = "setitem"
    DELITEM = "delitem"

@dataclasses.dataclass(frozen=True, slots=True)
class JournalledMappingEdit[K,V]:
    type: JournalledMappingEditType
    key : K
    value : V | None

class JournalledMapping[K,V](JournalledCollection[V, Mapping[K,V], dict[K,V], frozendict[K,V], JournalledMappingEdit[K,V]], MutableMapping[K,V]):
    # MARK: JournalledCollection ABC
    @override
    @classmethod
    def get_core_schema(cls, source, handler) -> CoreSchema:
        return PydanticFrozenDictAnnotation.__get_pydantic_core_schema__(source, handler)


    # MARK: Functionality
    def _append_journal(self, type : JournalledMappingEditType, key: K, value: V | None) -> None:
        self._journal.append(JournalledMappingEdit(type=type, key=key, value=value))
        self._on_edit()

    @override
    def __getitem__(self, key: K) -> V:
        return self._get_container()[key]

    @override
    def __setitem__(self, key: K, value: V) -> None:
        self._get_mut_container()[key] = value
        self._append_journal(JournalledMappingEditType.SETITEM, key, value)

    @override
    def __delitem__(self, key: K) -> None:
        del self._get_mut_container()[key]
        self._append_journal(JournalledMappingEditType.DELITEM, key, None)

    @override
    def __iter__(self) -> Iterator[K]:
        return iter(self._get_container())