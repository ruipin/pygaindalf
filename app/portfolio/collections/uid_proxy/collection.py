# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref
from abc import ABCMeta
from typing import override, cast as typing_cast, Self

from ....util.helpers import generics
from ....util.callguard import callguard_class

from ...models.entity import Entity


@callguard_class()
class UidProxyFrozenCollection[T_Proxy : Entity, T_Collection : object](metaclass=ABCMeta):
    def __init__(self, *, owner : object, field : str):
        self._owner = weakref.ref(owner)
        self._field = field

    def _get_owner(self) -> object:
        owner = self._owner()
        if owner is None:
            raise ValueError("Owner has been garbage collected")
        return owner

    def _get_field(self) -> T_Collection:
        return typing_cast(T_Collection, getattr(self._get_owner(), self._field))

    @classmethod
    def get_concrete_proxy_type(cls, source : type[Self] | None = None) -> type[T_Proxy]:
        return generics.get_concrete_parent_arg(source or cls, UidProxyFrozenCollection, "T_Proxy")

    @classmethod
    def get_concrete_collection_type(cls, source : type[Self] | None = None) -> type[T_Collection]:
        return generics.get_concrete_parent_arg(source or cls, UidProxyFrozenCollection, "T_Collection")

    @override
    def __str__(self) -> str:
        return str(self._get_field())

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self._get_field()!r}>"



class UidProxyCollection[T_Proxy : Entity, T_Collection : object, T_Mut_Collection : object](UidProxyFrozenCollection[T_Proxy, T_Collection], metaclass=ABCMeta):
    def _get_mut_field(self) -> T_Mut_Collection:
        field = self._get_field()
        if not isinstance(field, (mut_type := self.get_concrete_mutable_collection_type())):
            raise TypeError(f"Field '{self._get_owner()}.{self._field}' is not a {mut_type.__name__}.")
        return typing_cast(T_Mut_Collection, field)

    @classmethod
    def get_concrete_mutable_collection_type(cls, source : type[Self] | None = None) -> type[T_Mut_Collection]:
        return generics.get_concrete_parent_arg(source or cls, UidProxyCollection, "T_Mut_Collection")