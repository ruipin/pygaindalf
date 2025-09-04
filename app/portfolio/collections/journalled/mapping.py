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

type ImmutableMapping[K,V] = frozendict[K,V]

class JournalledMapping[K,V](JournalledCollection[ImmutableMapping[K,V], V], MutableMapping[K,V]):
    # MARK: JournalledCollection ABC
    @property
    @override
    def edited(self) -> bool:
        return self._mapping is not None

    @override
    def make_immutable(self) -> ImmutableMapping[K,V]:
        if self._mapping is not None:
            return frozendict(self._mapping)
        else:
            original = self._original
            if not isinstance(self._original, frozendict):
                original = frozendict(original)
            return typing_cast(ImmutableMapping[K,V], original)

    @override
    @classmethod
    def get_core_schema(cls, source, handler) -> CoreSchema:
        return PydanticFrozenDictAnnotation.__get_pydantic_core_schema__(source, handler)


    # MARK: Functionality
    def __init__(self, original : Mapping[K,V], /, **kwargs):
        super().__init__(**kwargs)
        self._original : Mapping[K,V] = original
        self._mapping : dict[K,V] | None = None
        self._journal : list[JournalledMappingEdit[K,V]] = []

    def _append_journal(self, type : JournalledMappingEditType, key: K, value: V | None) -> None:
        self._journal.append(JournalledMappingEdit(type=type, key=key, value=value))
        self._on_edit()

    def _copy_on_write(self) -> None:
        if self._mapping is not None:
            raise RuntimeError("Mapping is already modified")
        self._mapping = dict(self._original)

    @override
    def __getitem__(self, key: K) -> V:
        if self._mapping is None:
            return self._original[key]
        else:
            return self._mapping[key]

    @override
    def __setitem__(self, key: K, value: V) -> None:
        if self._mapping is None:
            self._copy_on_write()
        if self._mapping is None:
            raise RuntimeError("Mapping should have been copied on write")

        self._mapping[key] = value
        self._append_journal(JournalledMappingEditType.SETITEM, key, value)

    @override
    def __delitem__(self, key: K) -> None:
        if self._mapping is None:
            self._copy_on_write()
        if self._mapping is None:
            raise RuntimeError("Mapping should have been copied on write")

        del self._mapping[key]
        self._append_journal(JournalledMappingEditType.DELITEM, key, None)

    @override
    def __iter__(self) -> Iterator[K]:
        if self._mapping is None:
            return iter(self._original)
        else:
            return iter(self._mapping)

    @override
    def __len__(self):
        if self._mapping is None:
            return len(self._original)
        else:
            return len(self._mapping)

    @override
    def __str__(self) -> str:
        if self._mapping is None:
            return str(self._original)
        return str(self._mapping)

    @override
    def __repr__(self) -> str:
        if self._mapping is None:
            return repr(self._original)
        return repr(self._mapping)