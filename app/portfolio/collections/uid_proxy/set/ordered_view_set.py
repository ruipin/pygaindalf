# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, override, overload, Iterator, Self
from collections.abc import Sequence
from functools import cached_property

from .....util.helpers import generics

from ....models.uid import Uid
from ....models.entity import Entity
from ...ordered_view import OrderedViewSet, OrderedViewFrozenSet
from .generic_set import GenericUidProxySet, GenericUidProxyFrozenSet
from ..sequence import UidProxySequence



class UidProxyOrderedViewFrozenSet[T : Entity, T_Proxy_Seq : UidProxySequence](GenericUidProxyFrozenSet[T, OrderedViewFrozenSet[Uid]]):
    @classmethod
    def get_concrete_proxy_sequence_type(cls, source : type[Self] | None = None) -> type[T_Proxy_Seq]:
        return generics.get_concrete_parent_argument_origin(source or cls, UidProxyOrderedViewFrozenSet, 'T_Proxy_Seq')

    # MARK: OrderedViewSet
    @cached_property
    def sorted(self) -> Sequence[T]:
        return self.get_concrete_proxy_sequence_type()(owner=self._get_field(), field='sorted')

    def clear_sort_cache(self) -> None:
        self._get_field().clear_sort_cache()

    @overload
    def __getitem__(self, index: int) -> T: ...
    @overload
    def __getitem__(self, index: slice) -> Sequence[T]: ...
    def __getitem__(self, index: int | slice) -> T | Sequence[T]:
        return self.sorted[index]


class UidProxyOrderedViewSet[T : Entity, T_Proxy_Seq : UidProxySequence](UidProxyOrderedViewFrozenSet[T, T_Proxy_Seq], GenericUidProxySet[T, OrderedViewFrozenSet[Uid], OrderedViewSet[Uid]]):
    pass