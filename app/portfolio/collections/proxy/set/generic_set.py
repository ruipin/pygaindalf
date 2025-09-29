# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import MutableSet
from collections.abc import Set as AbstractSet
from typing import override

from ..collection import ProxyCollection, ProxyMutableCollection
from ..iterable import ProxyIterable


class GenericProxySet[
    T_Item: object,
    T_Proxy: object,
    T_Collection: AbstractSet,
](
    ProxyIterable[T_Item, T_Proxy, T_Collection],
    ProxyCollection[T_Item, T_Proxy, T_Collection],
    AbstractSet[T_Proxy],
    metaclass=ABCMeta,
):
    pass


class GenericProxyMutableSet[
    T_Item: object,
    T_Proxy: object,
    T_Collection: AbstractSet,
    T_Mut_Collection: MutableSet,
](
    GenericProxySet[T_Item, T_Proxy, T_Collection],
    ProxyMutableCollection[T_Item, T_Proxy, T_Collection, T_Mut_Collection],
    MutableSet[T_Proxy],
    metaclass=ABCMeta,
):
    @override
    def add(self, value: T_Proxy) -> None:
        item = self._convert_proxy_to_item(value)
        self._get_mut_field().add(item)

    @override
    def discard(self, value: T_Proxy) -> None:
        item = self._convert_proxy_to_item(value)
        self._get_mut_field().discard(item)

    @override
    def clear(self) -> None:
        self._get_mut_field().clear()
