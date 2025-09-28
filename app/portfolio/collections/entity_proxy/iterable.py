# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from typing import override
from collections.abc import Iterable

from ...models.entity import Entity, EntityProxy

from ..proxy import ProxyIterable

from .base import EntityProxyBase


class EntityProxyIterable[
    T_Item : Entity,
    T_Proxy : EntityProxy,
    T_Iterable : Iterable
](
    EntityProxyBase[T_Item, T_Proxy, T_Iterable],
    ProxyIterable[T_Item, T_Proxy, T_Iterable],
    metaclass=ABCMeta
):
    pass