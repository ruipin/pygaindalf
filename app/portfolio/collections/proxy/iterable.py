# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import Iterable, Iterator
from typing import override

from ....util.callguard import callguard_class
from .base import ProxyBase


@callguard_class()
class ProxyIterable[
    T_Item: object,
    T_Proxy: object,
    T_Iterable: Iterable,
](
    ProxyBase[T_Item, T_Proxy, T_Iterable],
    Iterable[T_Proxy],
    metaclass=ABCMeta,
):
    @override
    def __iter__(self) -> Iterator[T_Proxy]:
        for item in iter(self._get_field()):
            yield self._convert_item_to_proxy(item)
