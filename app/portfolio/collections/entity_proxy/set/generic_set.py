# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Set, MutableSet

from ....models.entity import Entity, EntityProxy

from ...proxy import GenericProxySet, GenericProxyMutableSet

from ..collection import EntityProxyCollection, EntityProxyMutableCollection
from ..iterable import EntityProxyIterable



class GenericEntityProxySet[
    T_Item : Entity,
    T_Proxy : EntityProxy,
    T_Collection : Set,
](
    EntityProxyIterable[T_Item, T_Proxy, T_Collection],
    EntityProxyCollection[T_Item, T_Proxy, T_Collection],
    GenericProxySet[T_Item, T_Proxy, T_Collection],
):
    pass


class GenericEntityProxyMutableSet[
    T_Item : Entity,
    T_Proxy : EntityProxy,
    T_Collection : Set,
    T_Mut_Collection : MutableSet,
](
    EntityProxyMutableCollection[T_Item, T_Proxy, T_Collection, T_Mut_Collection],
    GenericProxyMutableSet[T_Item, T_Proxy, T_Collection, T_Mut_Collection],
    GenericEntityProxySet[T_Item, T_Proxy, T_Collection],
):
    pass