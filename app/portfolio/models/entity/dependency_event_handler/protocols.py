# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable


if TYPE_CHECKING:
    from ..entity_record import EntityRecord
    from .type_enum import EntityDependencyEventType


# MARK: Protocols
@runtime_checkable
class EntityDependencyEventEntityMatcher[
    T_Owner: EntityRecord,
    T_Record: EntityRecord,
](Protocol):
    @staticmethod
    def __call__(owner: T_Owner, record: T_Record) -> bool: ...


@runtime_checkable
class EntityDependencyEventAttributeMatcher[
    T_Owner: EntityRecord,
    T_Record: EntityRecord,
](Protocol):
    @staticmethod
    def __call__(owner: T_Owner, record: T_Record, attribute: str, value: Any) -> bool: ...


@runtime_checkable
class EntityDependencyEventHandler[
    T_Owner: EntityRecord,
    T_Record: EntityRecord,
](Protocol):
    @staticmethod
    def __call__(owner: T_Owner, event: EntityDependencyEventType, record: T_Record, *, matched_attributes: frozenset[str] | None = None) -> None: ...
