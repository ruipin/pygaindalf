# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import ABCMeta
from collections.abc import Sized
from typing import override

from ....util.callguard import callguard_class
from .base import ProxyBase


@callguard_class()
class ProxySized[
    T_Item: object,
    T_Proxy: object,
    T_Sized: Sized,
](
    ProxyBase[T_Item, T_Proxy, T_Sized],
    Sized,
    metaclass=ABCMeta,
):
    @override
    def __len__(self) -> int:
        return len(self._get_field())
