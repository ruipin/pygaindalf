# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import MutableSequence, Sequence

from ....util.models.uid import Uid
from ..proxy import ProxyMutableSequence, ProxySequence
from .collection import T_ProxyBase, UidProxyCollection, UidProxyMutableCollection


class UidProxySequence[
    T: T_ProxyBase,
](
    UidProxyCollection[T, Sequence[Uid]],
    ProxySequence[Uid, T],
):
    pass


class UidProxyMutableSequence[
    T: T_ProxyBase,
](
    UidProxyMutableCollection[T, Sequence[Uid], MutableSequence[Uid]],
    ProxyMutableSequence[Uid, T],
):
    pass
