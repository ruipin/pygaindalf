# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import Collection
from typing import override

from ...models.entity import Entity, EntityProxy
from ..proxy import ProxyCollection, ProxyMutableCollection
from .base import EntityProxyBase


class EntityProxyCollection[
    T_Item: Entity,
    T_Proxy: EntityProxy,
    T_Collection: Collection,
](
    EntityProxyBase[T_Item, T_Proxy, T_Collection],
    ProxyCollection[T_Item, T_Proxy, T_Collection],
    metaclass=ABCMeta,
):
    @override
    def _do_convert_item_to_proxy(self, item: T_Item, item_type: type[T_Item], proxy_type: type[T_Proxy]) -> T_Proxy:
        return item.proxy

    @override
    def _do_convert_proxy_to_item(self, proxy: T_Proxy, proxy_type: type[T_Proxy], item_type: type[T_Item]) -> T_Item:
        return proxy.entity


class EntityProxyMutableCollection[
    T_Item: Entity,
    T_Proxy: EntityProxy,
    T_Collection: Collection,
    T_Mut_Collection: Collection,
](
    EntityProxyCollection[T_Item, T_Proxy, T_Collection],
    ProxyMutableCollection[T_Item, T_Proxy, T_Collection, T_Mut_Collection],
    metaclass=ABCMeta,
):
    pass
