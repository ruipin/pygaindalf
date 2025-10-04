# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import MutableSet
from collections.abc import Set as AbstractSet

from ....util.uid import Uid
from ...proxy import GenericProxyMutableSet, GenericProxySet
from ..collection import T_ProxyBase, UidProxyCollection, UidProxyMutableCollection


class GenericUidProxySet[
    T: T_ProxyBase,
    T_Collection: AbstractSet[Uid],
](
    UidProxyCollection[T, T_Collection],
    GenericProxySet[Uid, T, T_Collection],
):
    pass


class GenericUidProxyMutableSet[
    T: T_ProxyBase,
    T_Collection: AbstractSet[Uid],
    T_Mut_Collection: MutableSet[Uid],
](
    UidProxyMutableCollection[T, T_Collection, T_Mut_Collection],
    GenericProxyMutableSet[Uid, T, T_Collection, T_Mut_Collection],
    GenericUidProxySet[T, T_Collection],
):
    pass
