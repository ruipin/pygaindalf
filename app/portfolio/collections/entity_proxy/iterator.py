# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import Iterator

from ...models.entity import Entity, EntityProxy
from ..proxy import ProxyIterator
from .base import EntityProxyBase


class EntityProxyIterator[
    T_Item: Entity,
    T_Proxy: EntityProxy,
    T_Iterator: Iterator,
](
    EntityProxyBase[T_Item, T_Proxy, T_Iterator],
    ProxyIterator[T_Item, T_Proxy, T_Iterator],
    metaclass=ABCMeta,
):
    pass
