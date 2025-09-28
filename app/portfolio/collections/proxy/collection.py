# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref

from abc import ABCMeta, abstractmethod
from collections.abc import Collection, Iterable
from typing import override, cast as typing_cast, overload

from ....util.helpers import generics
from ....util.callguard import callguard_class

from .iterable import ProxyIterable
from .container import ProxyContainer
from .sized import ProxySized


@callguard_class()
class ProxyCollection[
    T_Item : object,
    T_Proxy : object,
    T_Collection : Collection
](
    ProxyContainer[T_Item, T_Proxy, T_Collection],
    ProxySized[T_Item, T_Proxy, T_Collection],
    Collection,
    Iterable,
    metaclass=ABCMeta
):
    pass


class ProxyMutableCollection[
    T_Item : object,
    T_Proxy : object,
    T_Collection : Collection,
    T_Mut_Collection : Collection,
](
    ProxyCollection[T_Item, T_Proxy, T_Collection],
    metaclass=ABCMeta
):
    def _get_mut_field(self) -> T_Mut_Collection:
        field = self._get_field()
        if not isinstance(field, (mut_type := self.get_mutable_collection_type(origin=True))):
            raise TypeError(f"Field '{self._get_instance()}.{self._field}' is not a {mut_type.__name__}.")
        return typing_cast(T_Mut_Collection, field)

    get_mutable_collection_type = generics.GenericIntrospectionMethod[T_Mut_Collection]()