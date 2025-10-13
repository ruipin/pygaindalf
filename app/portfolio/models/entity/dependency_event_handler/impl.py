# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Any, override

from ..entity_record import EntityRecord
from .base import EntityDependencyEventHandlerBase


if TYPE_CHECKING:
    from .type_enum import EntityDependencyEventType


# MARK: Implementation Record
class EntityDependencyEventHandlerImpl[
    T_Owner: EntityRecord,
    T_Record: EntityRecord,
](
    EntityDependencyEventHandlerBase[T_Owner, T_Record],
    metaclass=ABCMeta,
):
    @staticmethod
    @override
    def entity_matchers(owner: T_Owner, record: T_Record) -> bool:
        return True

    @staticmethod
    @override
    def attribute_matchers(owner: T_Owner, record: T_Record, attribute: str, value: Any) -> bool:
        return True

    @staticmethod
    @override
    @abstractmethod
    def handler(owner: T_Owner, event: EntityDependencyEventType, record: T_Record, *, matched_attributes: frozenset[str] | None = None) -> None:
        msg = "EntityDependencyEventHandlerImplRecord.handler must be overridden in subclasses."
        raise NotImplementedError(msg)

    def __init_subclass__(cls, *args, init: bool = False, **kwargs) -> None:
        super().__init_subclass__(*args, **kwargs)

        if (on_updated := getattr(cls, "on_updated", None)) is None or not isinstance(on_updated, bool):
            msg = f"{cls.__name__} must define the on_updated class attribute."
            raise NotImplementedError(msg)

        if (on_deleted := getattr(cls, "on_deleted", None)) is None or not isinstance(on_deleted, bool):
            msg = f"{cls.__name__} must define the on_deleted class attribute."
            raise NotImplementedError(msg)
