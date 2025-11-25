# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import dataclasses

from collections.abc import Iterator, Mapping, MutableMapping
from enum import Enum
from typing import (
    TYPE_CHECKING,
    override,
)

from ....util.helpers.frozendict import PydanticFrozenDictAnnotation, frozendict
from ....util.models.uid import Uid, UidProtocol
from .collection import JournalledCollection


if TYPE_CHECKING:
    from pydantic_core import CoreSchema


class JournalledMappingEditType(Enum):
    SETITEM = "setitem"
    DELITEM = "delitem"


@dataclasses.dataclass(frozen=True, slots=True)
class JournalledMappingEdit[K, V]:
    type: JournalledMappingEditType
    key: K
    value: V | Uid | None

    @override
    def __str__(self) -> str:
        return f"{self.type.value}({self.key}: {self.value})"

    @override
    def __repr__(self) -> str:
        return self.__str__()


class JournalledMapping[K, V](JournalledCollection[V, Mapping[K, V], dict[K, V], frozendict[K, V], JournalledMappingEdit[K, V]], MutableMapping[K, V]):
    # MARK: JournalledCollection ABC
    @override
    @classmethod
    def get_core_schema(cls, source, handler) -> CoreSchema:  # noqa: ANN001
        return PydanticFrozenDictAnnotation.__get_pydantic_core_schema__(source, handler)

    # MARK: Functionality
    def _append_journal(self, type: JournalledMappingEditType, key: K, value: V | None) -> None:  # NOQA: A002
        self._journal.append(JournalledMappingEdit(type=type, key=key, value=value.uid if isinstance(value, UidProtocol) else value))
        self._on_edit()

    @override
    def __getitem__(self, key: K) -> V:
        return self._get_container()[key]

    @override
    def __setitem__(self, key: K, value: V) -> None:
        try:
            if self._get_container()[key] == value:
                return
        except KeyError:
            pass

        self._get_mut_container()[key] = value
        self._append_journal(JournalledMappingEditType.SETITEM, key, value)

    @override
    def __delitem__(self, key: K) -> None:
        if key not in self._get_container():
            return

        del self._get_mut_container()[key]
        self._append_journal(JournalledMappingEditType.DELITEM, key, None)

    @override
    def __iter__(self) -> Iterator[K]:
        return iter(self._get_container())
