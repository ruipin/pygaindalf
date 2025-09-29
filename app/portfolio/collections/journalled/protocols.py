# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, Protocol, runtime_checkable


if TYPE_CHECKING:
    from ..ordered_view.protocols import SortKeyProtocol
    from .collection import JournalledCollection


@runtime_checkable
class JournalledCollectionHooksProtocol(Protocol):
    def on_journalled_collection_edit(self, collection: JournalledCollection) -> None: ...


@runtime_checkable
class OnItemUpdatedCollectionProtocol(Protocol):
    def __contains__(self, item: object) -> bool: ...
    def on_item_updated(self, old_item: SortKeyProtocol, new_item: SortKeyProtocol) -> None: ...
