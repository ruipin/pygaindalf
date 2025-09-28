# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref

from abc import ABCMeta, abstractmethod
from collections.abc import Container
from typing import override, cast as typing_cast, overload

from ....util.helpers import generics
from ....util.callguard import callguard_class

from .base import ProxyBase


@callguard_class()
class ProxyContainer[
    T_Item : object,
    T_Proxy : object,
    T_Container : Container,
](
    ProxyBase[T_Item, T_Proxy, T_Container],
    Container,
    metaclass=ABCMeta
):
    @override
    def __contains__(self, item: object) -> bool:
        proxy_type = self.get_proxy_type(origin=True)
        if not isinstance(item, proxy_type):
            return False

        converted = self._convert_proxy_to_item(item)
        return converted in self._get_field()