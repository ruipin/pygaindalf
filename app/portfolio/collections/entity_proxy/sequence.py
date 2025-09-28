# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Sequence, MutableSequence

from ...models.entity import Entity, EntityProxy

from ..proxy import ProxySequence, ProxyMutableSequence

from .collection import EntityProxyCollection, EntityProxyMutableCollection
from .iterable import EntityProxyIterable



class EntityProxySequence[
    T_Item : Entity,
    T_Proxy : EntityProxy,
](
    EntityProxyIterable[T_Item, T_Proxy, Sequence[T_Item]],
    EntityProxyCollection[T_Item, T_Proxy, Sequence[T_Item]],
    ProxySequence[T_Item, T_Proxy],
):
    pass



class EntityProxyMutableSequence[
    T_Item : Entity,
    T_Proxy : EntityProxy,
](
    EntityProxyMutableCollection[T_Item, T_Proxy, Sequence[T_Item], MutableSequence[T_Item]],
    ProxyMutableSequence[T_Item, T_Proxy],
):
    pass