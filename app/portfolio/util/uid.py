# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import random
import re
import sys

from collections.abc import Hashable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, Self, override, runtime_checkable

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ...util.helpers import script_info


if TYPE_CHECKING:
    from ..models.entity import Entity, EntityRecord


UID_SEPARATOR = ":"
UID_ID_REGEX = re.compile(r"^[a-zA-Z0-9@_#-]+$")


# MARK: Uid Class
@dataclass(frozen=True, slots=True)
class Uid:
    namespace: str = "DEFAULT"
    id: Hashable = field(default_factory=lambda: random.getrandbits(sys.hash_info.width))

    def __post_init__(self) -> None:
        if not self.namespace or not isinstance(self.namespace, str):
            msg = "Namespace must be a non-empty string."
            raise ValueError(msg)
        if re.search(UID_ID_REGEX, self.namespace) is None:
            msg = f"ID '{self.namespace}' is not valid. It must match the pattern '{UID_ID_REGEX.pattern}'."
            raise ValueError(msg)

        if self.id is None:
            msg = "ID must be an integer or string."
            raise ValueError(msg)
        if re.search(UID_ID_REGEX, self.id_as_str) is None:
            msg = f"ID '{self.id}' is not valid. When converted to string, it must match the pattern '{UID_ID_REGEX.pattern}'."
            raise ValueError(msg)

    def as_tuple(self) -> tuple[str, Hashable]:
        return (self.namespace, self.id)

    @property
    def id_as_str(self) -> str:
        """Returns the ID as a string, suitable for display."""
        if isinstance(self.id, int):
            return format(self.id, "x")
        else:
            return str(self.id)

    @override
    def __hash__(self) -> int:
        return hash(self.as_tuple())

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Uid):
            return False
        return self.as_tuple() == other.as_tuple()

    @override
    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Uid):
            return NotImplemented
        return self.as_tuple() < other.as_tuple()

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Uid):
            return NotImplemented
        return self.as_tuple() <= other.as_tuple()

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Uid):
            return NotImplemented
        return self.as_tuple() > other.as_tuple()

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Uid):
            return NotImplemented
        return self.as_tuple() >= other.as_tuple()

    @property
    def entity_or_none(self) -> Entity | None:
        from ..models.entity import Entity

        return Entity.by_uid_or_none(self)

    @property
    def entity(self) -> Entity:
        from ..models.entity import Entity

        return Entity.by_uid(self)

    @property
    def record_or_none(self) -> EntityRecord | None:
        from ..models.entity import EntityRecord

        return EntityRecord.by_uid_or_none(self)

    @property
    def record(self) -> EntityRecord:
        from ..models.entity import EntityRecord

        return EntityRecord.by_uid(self)

    @override
    def __str__(self) -> str:
        return f"{self.namespace}{UID_SEPARATOR}{self.id_as_str}"

    @override
    def __repr__(self) -> str:
        return f"<Uid: {self!s}>"

    @classmethod
    def __get_pydantic_core_schema__(cls, source: type[Any], handler: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.is_instance_schema(
            cls,
            serialization=core_schema.to_string_ser_schema(
                when_used="always",
            ),
        )


# MARK: Incrementing Uid Factory
class IncrementingUidFactory:
    _instance: ClassVar[IncrementingUidFactory]
    counters: dict[str, int]

    def __new__(cls) -> Self:
        instance = getattr(cls, "_instance", None)
        if not instance:
            instance = cls._instance = super().__new__(cls)
        return instance

    def __init__(self) -> None:
        # Ensure singleton behavior for each namespace
        if not hasattr(self, "namespace"):
            self.counters = {}

    def next(self, namespace: str, /, *, increment: bool = True) -> Uid:
        # Warning: This method is not thread-safe.
        counter = self.counters.get(namespace, 1)
        uid = Uid(namespace=namespace, id=counter)
        if increment:
            self.counters[namespace] = counter + 1
        return uid

    if script_info.is_unit_test():

        def reset(self) -> None:
            self.counters.clear()


# MARK: Protocol
@runtime_checkable
class UidProtocol(Protocol):
    @property
    def uid(self) -> Uid: ...
