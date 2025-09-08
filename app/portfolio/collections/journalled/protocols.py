# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from .collection import JournalledCollection


@runtime_checkable
class JournalledCollectionHooksProtocol(Protocol):
    def on_journalled_collection_edit(self, collection : JournalledCollection) -> None: ...