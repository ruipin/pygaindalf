# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import Collection
from typing import override

from ...models.entity import Entity
from ...util.uid import Uid

from ..proxy import ProxyCollection, ProxyMutableCollection


class UidProxyCollection[
    T_Proxy : Entity,
    T_Collection : Collection,
](
    ProxyCollection[Uid, T_Proxy, T_Collection],
    metaclass=ABCMeta
):
    @override
    def _do_convert_item_to_proxy(self, item : Uid, item_type : type[Uid], proxy_type : type[T_Proxy]) -> T_Proxy:
        proxy = proxy_type.by_uid_or_none(item)
        if proxy is None:
            raise KeyError(f"No {proxy_type.__name__} with UID {item} found")
        return proxy

    @override
    def _do_convert_proxy_to_item(self, proxy : T_Proxy, proxy_type : type[T_Proxy], item_type : type[Uid]) -> Uid:
        return proxy.uid



class UidProxyMutableCollection[
    T_Proxy : Entity,
    T_Collection : Collection,
    T_Mut_Collection : Collection,
](
    UidProxyCollection[T_Proxy, T_Collection],
    ProxyMutableCollection[Uid, T_Proxy, T_Collection, T_Mut_Collection],
    metaclass=ABCMeta
):
    pass