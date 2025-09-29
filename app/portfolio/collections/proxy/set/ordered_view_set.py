# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import Sequence
from functools import cached_property
from typing import overload

from .....util.helpers import generics
from ...ordered_view import OrderedViewMutableSet, OrderedViewSet
from ..sequence import ProxySequence
from .generic_set import GenericProxyMutableSet, GenericProxySet


class ProxyOrderedViewSet[
    T_Item: object,
    T_Proxy: object,
    T_Proxy_Sequence: ProxySequence,
](
    GenericProxySet[T_Item, T_Proxy, OrderedViewSet[T_Item]],
    metaclass=ABCMeta,
):
    get_proxy_sequence_type = generics.GenericIntrospectionMethod[T_Proxy_Sequence]()

    # MARK: OrderedViewSet
    @cached_property
    def sorted(self) -> ProxySequence[T_Item, T_Proxy]:
        proxy_seq_type = self.get_proxy_sequence_type()
        return proxy_seq_type(instance=self._get_field(), field="sorted")

    def clear_sort_cache(self) -> None:
        self._get_field().clear_sort_cache()

    @overload
    def __getitem__(self, index: int) -> T_Proxy: ...
    @overload
    def __getitem__(self, index: slice) -> Sequence[T_Proxy]: ...
    def __getitem__(self, index: int | slice) -> T_Proxy | Sequence[T_Proxy]:
        return self.sorted[index]


class ProxyOrderedViewMutableSet[
    T_Item: object,
    T_Proxy: object,
    T_Proxy_Sequence: ProxySequence,
](
    ProxyOrderedViewSet[T_Item, T_Proxy, T_Proxy_Sequence],
    GenericProxyMutableSet[T_Item, T_Proxy, OrderedViewSet[T_Item], OrderedViewMutableSet[T_Item]],
):
    pass
