# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, override, overload, Iterable
from collections.abc import Sequence, MutableSequence

from ...models.uid import Uid
from .collection import UidProxyCollection, UidProxyFrozenCollection

from ...models.entity import Entity


class UidProxyFrozenSequence[T : Entity](Sequence[T], UidProxyFrozenCollection[T, Sequence[Uid]]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @override
    def __len__(self) -> int:
        return len(self._get_field())

    @overload
    def __getitem__(self, index: int) -> T: ...
    @overload
    def __getitem__(self, index: slice) -> MutableSequence[T]: ...
    @override
    def __getitem__(self, index: int | slice) -> T | MutableSequence[T]:
        if isinstance(index, slice):
            raise NotImplementedError("Sliced read access not implemented yet")

        uid = self._get_field()[index]
        if uid is None:
            raise ValueError(f"UID at index {index} is None")
        if not isinstance(uid, Uid):
            raise TypeError(f"Expected Uid, got {type(uid)}")

        return self.get_concrete_proxy_type().by_uid(uid)



class UidProxySequence[T : Entity](MutableSequence[T], UidProxyFrozenSequence[T], UidProxyCollection[T, Sequence[Uid], MutableSequence[Uid]]):
    @overload
    def __setitem__(self, index: int, value: T) -> None: ...
    @overload
    def __setitem__(self, index: slice, value: Iterable[T]) -> None: ...
    @override
    def __setitem__(self, index: int | slice, value: T | Iterable[T]) -> None:
        if isinstance(index, slice):
            raise NotImplementedError("Sliced write access not implemented yet")

        if not isinstance(value, (proxy_type := self.get_concrete_proxy_type())):
            raise TypeError(f"Only single item assignment of type {proxy_type.__name__} is allowed")

        self._get_mut_field()[index] = value.uid

    @overload
    def __delitem__(self, index: int) -> None: ...
    @overload
    def __delitem__(self, index: slice) -> None: ...
    @override
    def __delitem__(self, index: int | slice) -> None:
        del self._get_mut_field()[index]

    @override
    def clear(self) -> None:
        self._get_mut_field().clear()

    @override
    def insert(self, index: int, value: T) -> None:
        if not isinstance(value, (proxy_type := self.get_concrete_proxy_type())):
            raise NotImplementedError(f"Value must have type {proxy_type.__name__}")

        self._get_mut_field().insert(index, value.uid)