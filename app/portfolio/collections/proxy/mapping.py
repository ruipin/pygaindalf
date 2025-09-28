# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override, Iterator
from collections.abc import Mapping, MutableMapping
from abc import ABCMeta

from .collection import ProxyCollection, ProxyMutableCollection


class ProxyMapping[
    K,
    V_Item : object,
    V_Proxy : object
](
    ProxyCollection[V_Item, V_Proxy, Mapping[K,V_Item]],
    Mapping[K,V_Proxy],
    metaclass=ABCMeta
):
    @override
    def __getitem__(self, key: K) -> V_Proxy:
        item = self._get_field()[key]
        return self._convert_item_to_proxy(item)

    @override
    def __iter__(self) -> Iterator[K]:
        return iter(self._get_field())



class ProxyMutableMapping[
    K,
    V_Item : object,
    V_Proxy : object
](
    ProxyMapping[K,V_Item,V_Proxy],
    ProxyMutableCollection[V_Item, V_Proxy, Mapping[K,V_Item], MutableMapping[K,V_Item]],
    MutableMapping[K,V_Proxy],
    metaclass=ABCMeta
):
    @override
    def __setitem__(self, key: K, value: V_Proxy) -> None:
        item = self._convert_proxy_to_item(value)
        self._get_mut_field()[key] = item

    @override
    def __delitem__(self, key: K) -> None:
        del self._get_mut_field()[key]