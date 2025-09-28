# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Set, MutableSet

from ....models.entity import Entity, EntityProxy

from ...proxy import ProxySet, ProxyMutableSet

from .generic_set import GenericEntityProxySet, GenericEntityProxyMutableSet


class EntityProxySet[
    T_Item : Entity,
    T_Proxy : EntityProxy,
](
    GenericEntityProxySet[T_Item, T_Proxy, Set[T_Item]]
):
    pass
ProxySet.register(EntityProxySet)


class EntityProxyMutableSet[
    T_Item : Entity,
    T_Proxy : EntityProxy,
](
    GenericEntityProxyMutableSet[T_Item, T_Proxy, Set[T_Item], MutableSet[T_Item]]
):
    pass
ProxyMutableSet.register(EntityProxyMutableSet)