# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import dataclasses

from typing import override, overload, Iterator
from enum import Enum
from collections.abc import MutableMapping, Mapping


class JournalledMappingEditType(Enum):
    SETITEM = "setitem"
    DELITEM = "delitem"

@dataclasses.dataclass(frozen=True, slots=True)
class JournalledMappingEdit[K,V]:
    type: JournalledMappingEditType
    key : K
    value : V | None


class JournalledMapping[K,V](MutableMapping[K,V]):
    def __init__(self, original : Mapping[K,V]):
        self._original : Mapping[K,V] = original
        self._mapping : dict[K,V] | None = None
        self._journal : list[JournalledMappingEdit[K,V]] = []

    def _append_journal(self, type : JournalledMappingEditType, key: K, value: V | None) -> None:
        self._journal.append(JournalledMappingEdit(type=type, key=key, value=value))

    @property
    def edited(self) -> bool:
        return self._mapping is not None

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

        self._append_journal(JournalledMappingEditType.SETITEM, key, value)
        self._mapping[key] = value

    @override
    def __delitem__(self, key: K) -> None:
        if self._mapping is None:
            self._copy_on_write()
        if self._mapping is None:
            raise RuntimeError("Mapping should have been copied on write")

        self._append_journal(JournalledMappingEditType.DELITEM, key, None)
        del self._mapping[key]

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