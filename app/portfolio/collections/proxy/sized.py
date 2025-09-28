# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref

from abc import ABCMeta, abstractmethod
from collections.abc import Sized
from typing import override, cast as typing_cast, overload

from ....util.helpers import generics
from ....util.callguard import callguard_class

from .base import ProxyBase


@callguard_class()
class ProxySized[
    T_Item : object,
    T_Proxy : object,
    T_Sized : Sized,
](
    ProxyBase[T_Item, T_Proxy, T_Sized],
    Sized,
    metaclass=ABCMeta
):
    @override
    def __len__(self) -> int:
        return len(self._get_field())