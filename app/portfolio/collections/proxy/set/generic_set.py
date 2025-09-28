# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override, Iterator
from collections.abc import Set, MutableSet
from abc import ABCMeta

from ..iterable import ProxyIterable
from ..collection import ProxyCollection, ProxyMutableCollection


class GenericProxySet[
    T_Item : object,
    T_Proxy : object,
    T_Collection : Set
](
    ProxyIterable[T_Item, T_Proxy, T_Collection],
    ProxyCollection[T_Item, T_Proxy, T_Collection],
    Set[T_Proxy],
    metaclass=ABCMeta
):
    pass


class GenericProxyMutableSet[
    T_Item : object,
    T_Proxy : object,
    T_Collection : Set,
    T_Mut_Collection : MutableSet
](
    GenericProxySet[T_Item, T_Proxy, T_Collection],
    ProxyMutableCollection[T_Item, T_Proxy, T_Collection, T_Mut_Collection],
    MutableSet[T_Proxy],
    metaclass=ABCMeta
):
    @override
    def add(self, value : T_Proxy) -> None:
        item = self._convert_proxy_to_item(value)
        self._get_mut_field().add(item)

    @override
    def discard(self, value : T_Proxy) -> None:
        item = self._convert_proxy_to_item(value)
        self._get_mut_field().discard(item)

    @override
    def clear(self) -> None:
        self._get_mut_field().clear()