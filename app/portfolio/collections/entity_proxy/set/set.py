# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import MutableSet
from collections.abc import Set as AbstractSet

from ....models.entity import Entity, EntityProxy
from ...proxy import ProxyMutableSet, ProxySet
from .generic_set import GenericEntityProxyMutableSet, GenericEntityProxySet


class EntityProxySet[
    T_Item: Entity,
    T_Proxy: EntityProxy,
](GenericEntityProxySet[T_Item, T_Proxy, AbstractSet[T_Item]]):
    pass


ProxySet.register(EntityProxySet)


class EntityProxyMutableSet[
    T_Item: Entity,
    T_Proxy: EntityProxy,
](GenericEntityProxyMutableSet[T_Item, T_Proxy, AbstractSet[T_Item], MutableSet[T_Item]]):
    pass


ProxyMutableSet.register(EntityProxyMutableSet)
