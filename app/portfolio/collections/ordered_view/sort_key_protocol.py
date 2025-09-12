# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison


@runtime_checkable
class SortKeyProtocol(Protocol):
    def sort_key(self) -> SupportsRichComparison: ...