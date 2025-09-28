# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from ....util.uid import Uid
from ....models.entity import Entity
from ...ordered_view import OrderedViewSet, OrderedViewMutableSet
from ...proxy import ProxyOrderedViewSet, ProxyOrderedViewMutableSet
from ..sequence import UidProxySequence
from .generic_set import GenericUidProxySet, GenericUidProxyMutableSet



class UidProxyOrderedViewSet[
    T : Entity
](
    GenericUidProxySet[T, OrderedViewSet[Uid]],
    ProxyOrderedViewSet[Uid, T, UidProxySequence[T]],
):
    pass


class UidProxyOrderedViewMutableSet[
    T : Entity
](
    GenericUidProxyMutableSet[T, OrderedViewSet[Uid], OrderedViewMutableSet[Uid]],
    ProxyOrderedViewMutableSet[Uid, T, UidProxySequence[T]],
):
    pass
UidProxyOrderedViewSet.register(UidProxyOrderedViewSet)