# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from typing import override
from collections.abc import Collection

from ...models.entity import Entity, EntityProxy

from ..proxy import ProxyBase


class EntityProxyBase[
    T_Item : Entity,
    T_Proxy : EntityProxy,
    T_Collection : object,
](
    ProxyBase[T_Item, T_Proxy, T_Collection],
    metaclass=ABCMeta
):
    @override
    def _do_convert_item_to_proxy(self, item : T_Item, item_type : type[T_Item], proxy_type : type[T_Proxy]) -> T_Proxy:
        return item.proxy

    @override
    def _do_convert_proxy_to_item(self, proxy : T_Proxy, proxy_type : type[T_Proxy], item_type : type[T_Item]) -> T_Item:
        return proxy.entity