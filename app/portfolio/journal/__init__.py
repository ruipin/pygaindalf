# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import runtime_checkable, Protocol

@runtime_checkable
class RefreshableEntitiesProtocol(Protocol):
    def refresh_entities(self) -> None: ...