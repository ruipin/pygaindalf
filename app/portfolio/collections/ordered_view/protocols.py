# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, Protocol, runtime_checkable


if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison

    from ..journalled.collection import JournalledCollection


@runtime_checkable
class SortKeyProtocol(Protocol):
    def sort_key(self) -> SupportsRichComparison: ...


@runtime_checkable
class HasJournalledTypeCollectionProtocol(Protocol):
    @classmethod
    def get_journalled_type(cls) -> type[JournalledCollection]: ...
    def __contains__(self, item: object) -> bool: ...
