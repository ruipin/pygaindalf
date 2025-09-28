# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Set, MutableSet

from ....models.entity import Entity
from ....util.uid import Uid

from ...proxy import GenericProxySet, GenericProxyMutableSet

from ..collection import UidProxyCollection, UidProxyMutableCollection



class GenericUidProxySet[
    T : Entity,
    T_Collection : Set[Uid]
](
    UidProxyCollection[T, T_Collection],
    GenericProxySet[Uid, T, T_Collection],
):
    pass


class GenericUidProxyMutableSet[
    T : Entity,
    T_Collection : Set[Uid],
    T_Mut_Collection : MutableSet[Uid]
](
    UidProxyMutableCollection[T, T_Collection, T_Mut_Collection],
    GenericProxyMutableSet[Uid, T, T_Collection, T_Mut_Collection],
    GenericUidProxySet[T, T_Collection],
):
    pass