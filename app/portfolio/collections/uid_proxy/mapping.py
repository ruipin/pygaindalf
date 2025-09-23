# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, override, Iterator
from collections.abc import Mapping, MutableMapping

from ...models.uid import Uid
from .collection import UidProxyCollection, UidProxyFrozenCollection

from ...models.entity import Entity


class UidProxyFrozenMapping[K, V : Entity](Mapping[K,V], UidProxyFrozenCollection[V, Mapping[K,Uid]]):
    @override
    def __getitem__(self, key: K) -> V:
        uid = self._get_field()[key]
        if uid is None:
            raise ValueError(f"UID with key '{key}' is None")
        if not isinstance(uid, Uid):
            raise TypeError(f"Expected Uid, got {type(uid)}")

        entity = self.get_concrete_proxy_type().by_uid_or_none(uid)
        if entity is None:
            raise KeyError(f"Entity with UID {uid} not found")

        return entity


    @override
    def __iter__(self) -> Iterator[K]:
        return iter(self._get_field())

    @override
    def __len__(self):
        return len(self._get_field())



class UidProxyMapping[K, V : Entity](MutableMapping[K,V], UidProxyFrozenMapping[K,V], UidProxyCollection[V, Mapping[K,Uid], MutableMapping[K,Uid]]):
    @override
    def __setitem__(self, key: K, value: V) -> None:
        self._get_mut_field()[key] = value.uid

    @override
    def __delitem__(self, key: K) -> None:
        del self._get_mut_field()[key]