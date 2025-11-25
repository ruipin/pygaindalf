# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import MutableSet
from collections.abc import Set as AbstractSet

from .....util.models.uid import Uid
from ...proxy import ProxyMutableSet, ProxySet
from ..collection import T_ProxyBase
from .generic_set import GenericUidProxyMutableSet, GenericUidProxySet


class UidProxySet[
    T: T_ProxyBase,
](
    GenericUidProxySet[T, AbstractSet[Uid]],
):
    pass


ProxySet.register(UidProxySet)


class UidProxyMutableSet[
    T: T_ProxyBase,
](
    GenericUidProxyMutableSet[T, AbstractSet[Uid], MutableSet[Uid]],
):
    pass


ProxyMutableSet.register(UidProxyMutableSet)
