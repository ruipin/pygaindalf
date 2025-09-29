# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import MutableSequence, Sequence

from ...models.entity import Entity
from ...util.uid import Uid
from ..proxy import ProxyMutableSequence, ProxySequence
from .collection import UidProxyCollection, UidProxyMutableCollection


class UidProxySequence[
    T: Entity,
](
    UidProxyCollection[T, Sequence[Uid]],
    ProxySequence[Uid, T],
):
    pass


class UidProxyMutableSequence[
    T: Entity,
](
    UidProxyMutableCollection[T, Sequence[Uid], MutableSequence[Uid]],
    ProxyMutableSequence[Uid, T],
):
    pass
