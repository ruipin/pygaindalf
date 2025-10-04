# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from ....util.uid import Uid
from ...ordered_view import OrderedViewMutableSet, OrderedViewSet
from ...proxy import ProxyOrderedViewMutableSet, ProxyOrderedViewSet
from ..collection import T_ProxyBase
from ..sequence import UidProxySequence
from .generic_set import GenericUidProxyMutableSet, GenericUidProxySet


class UidProxyOrderedViewSet[
    T: T_ProxyBase,
](
    GenericUidProxySet[T, OrderedViewSet[Uid]],
    ProxyOrderedViewSet[Uid, T, UidProxySequence[T]],
):
    pass


class UidProxyOrderedViewMutableSet[
    T: T_ProxyBase,
](
    GenericUidProxyMutableSet[T, OrderedViewSet[Uid], OrderedViewMutableSet[Uid]],
    ProxyOrderedViewMutableSet[Uid, T, UidProxySequence[T]],
):
    pass


UidProxyOrderedViewSet.register(UidProxyOrderedViewSet)
