# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from enum import StrEnum


# MARK: Enums
class EntityDependencyEventType(StrEnum):
    UPDATED = "updated"
    DELETED = "deleted"

    @property
    def updated(self) -> bool:
        return self is EntityDependencyEventType.UPDATED

    @property
    def deleted(self) -> bool:
        return self is EntityDependencyEventType.DELETED
