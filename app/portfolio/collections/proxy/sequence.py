# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override, overload, Iterable, cast as typing_cast
from collections.abc import Sequence, MutableSequence
from abc import ABCMeta

from .iterable import ProxyIterable
from .collection import ProxyCollection, ProxyMutableCollection


class ProxySequence[
    T_Item : object,
    T_Proxy : object
](
    ProxyIterable[T_Item, T_Proxy, Sequence[T_Item]],
    ProxyCollection[T_Item, T_Proxy, Sequence[T_Item]],
    Sequence[T_Proxy],
    metaclass=ABCMeta
):
    @overload
    def __getitem__(self, index: int) -> T_Proxy: ...
    @overload
    def __getitem__(self, index: slice) -> MutableSequence[T_Proxy]: ...
    @override
    def __getitem__(self, index: int | slice) -> T_Proxy | MutableSequence[T_Proxy]:
        if isinstance(index, slice):
            raise NotImplementedError("Sliced read access not implemented yet")

        item = self._get_field()[index]
        return self._convert_item_to_proxy(item)



class ProxyMutableSequence[
    T_Item : object,
    T_Proxy : object
](
    ProxySequence[T_Item, T_Proxy],
    ProxyMutableCollection[T_Item, T_Proxy, Sequence[T_Item], MutableSequence[T_Item]],
    MutableSequence[T_Proxy],
    metaclass=ABCMeta
):
    @overload
    def __setitem__(self, index: int, value: T_Proxy) -> None: ...
    @overload
    def __setitem__(self, index: slice, value: Iterable[T_Proxy]) -> None: ...
    @override
    def __setitem__(self, index: int | slice, value: T_Proxy | Iterable[T_Proxy]) -> None:
        if isinstance(index, slice):
            raise NotImplementedError("Sliced write access not implemented yet")
        value = typing_cast(T_Proxy, value) # since we checked it's not a slice

        item = self._convert_proxy_to_item(value)
        self._get_mut_field()[index] = item

    @overload
    def __delitem__(self, index: int) -> None: ...
    @overload
    def __delitem__(self, index: slice) -> None: ...
    @override
    def __delitem__(self, index: int | slice) -> None:
        del self._get_mut_field()[index]

    __getitem__ = ProxySequence.__getitem__ # pyright: ignore[reportAssignmentType]

    @override
    def clear(self) -> None:
        self._get_mut_field().clear()

    @override
    def insert(self, index: int, value: T_Proxy) -> None:
        item = self._convert_proxy_to_item(value)
        self._get_mut_field().insert(index, item)