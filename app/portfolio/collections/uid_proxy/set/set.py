# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, override, Iterator
from collections.abc import Set, MutableSet

from ....models.uid import Uid
from .generic_set import GenericUidProxySet

from ....models.entity import Entity


class UidProxySet[T : Entity](GenericUidProxySet[T, Set[Uid], MutableSet[Uid]]):
    pass