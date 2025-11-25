# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Mapping, MutableMapping

from ....util.models.uid import Uid
from ..proxy import ProxyMapping, ProxyMutableMapping
from .collection import T_ProxyBase, UidProxyCollection, UidProxyMutableCollection


class UidProxyMapping[
    K,
    V: T_ProxyBase,
](
    UidProxyCollection[V, Mapping[K, Uid]],
    ProxyMapping[K, Uid, V],
):
    pass


class UidProxyMutableMapping[
    K,
    V: T_ProxyBase,
](
    UidProxyMutableCollection[V, Mapping[K, Uid], MutableMapping[K, Uid]],
    ProxyMutableMapping[K, Uid, V],
):
    pass
