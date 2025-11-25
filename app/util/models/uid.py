# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import random
import re
import sys

from collections.abc import Hashable
from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol, Self, override, runtime_checkable

from pydantic import GetCoreSchemaHandler, PlainSerializer
from pydantic_core import CoreSchema, core_schema

from ..helpers import script_info


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

    @classmethod
    def from_string(cls, value: str) -> Uid:
        if UID_SEPARATOR not in value:
            msg = f"Invalid UID string: '{value}'"
            raise ValueError(msg)

        namespace, id_str = value.split(UID_SEPARATOR, maxsplit=1)

        # Try to parse id_str as an integer (hex), otherwise keep as string
        try:
            id_value: Hashable = int(id_str, 16)
        except ValueError:
            id_value = id_str

        return Uid(namespace=namespace, id=id_value)

    @classmethod
    def from_value(cls, value: Any) -> Uid:
        if isinstance(value, Uid):
            return value
        elif isinstance(value, str):
            return cls.from_string(value)
        else:
            msg = f"Cannot create Uid from value of type '{type(value).__name__}'"
            raise TypeError(msg)


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


@runtime_checkable
class VersionedUidProtocol(UidProtocol, Protocol):
    @property
    def version(self) -> int: ...


# MARK: Uid Serializer
def serialize_as_uid(v: Any) -> str:
    if isinstance(v, Uid):
        return str(v)
    if isinstance(v, UidProtocol):
        return str(v.uid)

    msg = f"Cannot serialize object of type {type(v)} as Uid."
    raise TypeError(msg)


AsUidSerializer = PlainSerializer(serialize_as_uid)
