# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from ....models.entity import Entity
from ....util.uid import Uid
from ...ordered_view import OrderedViewMutableSet, OrderedViewSet
from ...proxy import ProxyOrderedViewMutableSet, ProxyOrderedViewSet
from ..sequence import UidProxySequence
from .generic_set import GenericUidProxyMutableSet, GenericUidProxySet


class UidProxyOrderedViewSet[
    T: Entity,
](
    GenericUidProxySet[T, OrderedViewSet[Uid]],
    ProxyOrderedViewSet[Uid, T, UidProxySequence[T]],
):
    pass


class UidProxyOrderedViewMutableSet[
    T: Entity,
](
    GenericUidProxyMutableSet[T, OrderedViewSet[Uid], OrderedViewMutableSet[Uid]],
    ProxyOrderedViewMutableSet[Uid, T, UidProxySequence[T]],
):
    pass


UidProxyOrderedViewSet.register(UidProxyOrderedViewSet)
