# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import MutableSet
from collections.abc import Set as AbstractSet

from .generic_set import GenericProxyMutableSet, GenericProxySet


class ProxySet[
    T_Item: object,
    T_Proxy: object,
](
    GenericProxySet[T_Item, T_Proxy, AbstractSet[T_Item]],
    metaclass=ABCMeta,
):
    pass


class ProxyMutableSet[
    T_Item: object,
    T_Proxy: object,
](
    GenericProxyMutableSet[T_Item, T_Proxy, AbstractSet[T_Item], MutableSet[T_Item]],
    metaclass=ABCMeta,
):
    pass


ProxySet.register(ProxyMutableSet)
