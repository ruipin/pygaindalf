# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from .collection import JournalledCollection
    from ...journal.entity_journal import EntityJournal


@runtime_checkable
class JournalledCollectionHooksProtocol(Protocol):
    def on_journalled_collection_edit(self, collection : JournalledCollection) -> None: ...


@runtime_checkable
class OnItemUpdatedCollectionProtocol(Protocol):
    def __contains__(self, item) -> bool: ...
    def on_item_updated(self, old_item, new_item) -> None: ...