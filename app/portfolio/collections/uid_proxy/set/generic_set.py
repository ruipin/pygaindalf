# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, override, Iterator
from collections.abc import Set, MutableSet

from ....models.uid import Uid
from ..collection import UidProxyCollection

from ....models.entity import Entity


class GenericUidProxySet[T : Entity, T_Collection : Set[Uid], T_Mut_Collection : MutableSet[Uid]](MutableSet[T], UidProxyCollection[T, T_Collection, T_Mut_Collection]):
    @override
    def __contains__(self, value : object) -> bool:
        if isinstance(value, self.get_concrete_proxy_type()):
            return value.uid in self._get_field()
        return False

    @override
    def add(self, value : T) -> None:
        self._get_mut_field().add(value.uid)

    @override
    def discard(self, value : T) -> None:
        self._get_mut_field().discard(value.uid)

    @override
    def clear(self) -> None:
        self._get_mut_field().clear()

    @override
    def __iter__(self) -> Iterator[T]:
        proxy_type = self.get_concrete_proxy_type()

        for uid in self._get_field():
            entity = proxy_type.by_uid(uid)
            if entity is None:
                raise KeyError(f"Entity with UID {uid} not found")
            yield entity

    @override
    def __len__(self):
        return len(self._get_field())