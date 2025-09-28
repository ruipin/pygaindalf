# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Set, MutableSet

from ....util.uid import Uid
from ....models.entity import Entity

from ...proxy import ProxySet, ProxyMutableSet

from .generic_set import GenericUidProxySet, GenericUidProxyMutableSet


class UidProxySet[
    T : Entity
](
    GenericUidProxySet[T, Set[Uid]]
):
    pass
ProxySet.register(UidProxySet)


class UidProxyMutableSet[
    T : Entity
](
    GenericUidProxyMutableSet[T, Set[Uid], MutableSet[Uid]]
):
    pass
ProxyMutableSet.register(UidProxyMutableSet)