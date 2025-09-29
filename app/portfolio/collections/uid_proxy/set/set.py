# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import MutableSet
from collections.abc import Set as AbstractSet

from ....models.entity import Entity
from ....util.uid import Uid
from ...proxy import ProxyMutableSet, ProxySet
from .generic_set import GenericUidProxyMutableSet, GenericUidProxySet


class UidProxySet[
    T: Entity,
](
    GenericUidProxySet[T, AbstractSet[Uid]],
):
    pass


ProxySet.register(UidProxySet)


class UidProxyMutableSet[
    T: Entity,
](
    GenericUidProxyMutableSet[T, AbstractSet[Uid], MutableSet[Uid]],
):
    pass


ProxyMutableSet.register(UidProxyMutableSet)
