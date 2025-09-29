# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import ABCMeta
from collections.abc import Iterator
from typing import override

from ....util.callguard import callguard_class
from .base import ProxyBase


@callguard_class()
class ProxyIterator[
    T_Item: object,
    T_Proxy: object,
    T_Iterator: Iterator,
](
    ProxyBase[T_Item, T_Proxy, T_Iterator],
    Iterator[T_Proxy],
    metaclass=ABCMeta,
):
    @override
    def __next__(self) -> T_Proxy:
        item = next(self._get_field())
        return self._convert_item_to_proxy(item)
