# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Mapping, MutableMapping

from ...util.uid import Uid
from ...models.entity import Entity

from ..proxy import ProxyMapping, ProxyMutableMapping

from .collection import UidProxyCollection, UidProxyMutableCollection




class UidProxyMapping[
    K,
    V : Entity
](
    UidProxyCollection[V, Mapping[K,Uid]],
    ProxyMapping[K, Uid, V],
):
    pass



class UidProxyMutableMapping[
    K,
    V : Entity
](
    UidProxyMutableCollection[V, Mapping[K,Uid], MutableMapping[K,Uid]],
    ProxyMutableMapping[K,Uid,V],
):
    pass