# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Set, MutableSet
from abc import ABCMeta

from .generic_set import GenericProxySet, GenericProxyMutableSet


class ProxySet[
    T_Item : object,
    T_Proxy : object
](
    GenericProxySet[T_Item, T_Proxy, Set[T_Item]],
    metaclass=ABCMeta
):
    pass

class ProxyMutableSet[
    T_Item : object,
    T_Proxy : object
](
    GenericProxyMutableSet[T_Item, T_Proxy, Set[T_Item], MutableSet[T_Item]],
    metaclass=ABCMeta
):
    pass
ProxySet.register(ProxyMutableSet)