# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, override, Iterator
from collections.abc import Set, MutableSet

from ....models.uid import Uid
from .generic_set import GenericUidProxySet, GenericUidProxyFrozenSet

from ....models.entity import Entity


class UidProxyFrozenSet[T : Entity](GenericUidProxyFrozenSet[T, Set[Uid]]):
    pass

class UidProxySet[T : Entity](UidProxyFrozenSet[T], GenericUidProxySet[T, Set[Uid], MutableSet[Uid]]):
    pass