# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref
import typing
from abc import ABCMeta
from collections.abc import Collection

from ....util.helpers import generics

from ...models.entity import Entity
from ...models.uid import Uid


class UidProxyCollection[T_Proxy : Entity, T_Collection : object, T_Mut_Collection : object](metaclass=ABCMeta):
    def __init__(self, *, owner : Entity, field : str):
        self._owner = weakref.ref(owner)
        self._field = field

    def _get_owner(self) -> Entity:
        owner = self._owner()
        if owner is None:
            raise ValueError("Owner has been garbage collected")
        return owner

    def _get_field(self) -> T_Collection:
        return typing.cast(T_Collection, getattr(self._get_owner(), self._field))

    def _get_mut_field(self) -> T_Mut_Collection:
        field = self._get_field()
        if not isinstance(field, (mut_type := self.get_concrete_mutable_collection_type())):
            raise TypeError(f"Field '{self._get_owner()}.{self._field}' is not a {mut_type.__name__}. Please ensure you start a journal session before modifying it.")
        return typing.cast(T_Mut_Collection, field)

    @classmethod
    def get_concrete_proxy_type(cls) -> type[T_Proxy]:
        return generics.get_concrete_parent_arg(cls, UidProxyCollection, "T_Proxy")

    @classmethod
    def get_concrete_collection_type(cls) -> type[T_Collection]:
        return generics.get_concrete_parent_arg(cls, UidProxyCollection, "T_Collection")

    @classmethod
    def get_concrete_mutable_collection_type(cls) -> type[T_Collection]:
        return generics.get_concrete_parent_arg(cls, UidProxyCollection, "T_Mut_Collection")