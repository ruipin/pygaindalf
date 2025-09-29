# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Mapping, MutableMapping
from typing import Any

from ...models.entity import Entity, EntityProxy
from ..proxy import ProxyMapping, ProxyMutableMapping
from .collection import EntityProxyCollection, EntityProxyMutableCollection


class EntityProxyMapping[
    V_Item: Entity,
    V_Proxy: EntityProxy,
](
    EntityProxyCollection[V_Item, V_Proxy, Mapping[Any, V_Item]],
    ProxyMapping[Any, V_Item, V_Proxy],
):
    pass


class EntityProxyMutableMapping[
    V_Item: Entity,
    V_Proxy: EntityProxy,
](
    EntityProxyMutableCollection[V_Item, V_Proxy, Mapping[Any, V_Item], MutableMapping[Any, V_Item]],
    ProxyMutableMapping[Any, V_Item, V_Proxy],
):
    pass
