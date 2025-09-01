# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import dataclasses
import types
from abc import ABCMeta, abstractmethod
from collections.abc import Collection
from typing import (Any, TypeVar, Self, Protocol, runtime_checkable,
    get_args as typing_get_args,
    cast as typing_cast,
    get_origin as typing_get_origin,
)
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ....util.helpers import generics


@runtime_checkable
class GetPydanticCoreSchemaProtocol(Protocol):
    @classmethod
    def __get_pydantic_core_schema__(cls, source: type[Any], handler: GetCoreSchemaHandler) -> CoreSchema: ...


class JournalledCollection[T_Immutable : Collection, T_Value : Any](metaclass=ABCMeta):
    @property
    @abstractmethod
    def edited(self) -> bool:
        raise NotImplementedError("Subclasses must implement 'edited' property")

    @abstractmethod
    def make_immutable(self) -> T_Immutable:
        raise NotImplementedError("Subclasses must implement 'make_immutable' method")

    @classmethod
    @abstractmethod
    def get_core_schema(cls, source: type[Self], handler: GetCoreSchemaHandler) -> CoreSchema:
        raise NotImplementedError("Subclasses must implement 'get_core_schema' method")

    @classmethod
    def get_concrete_immutable_type(cls) -> type[T_Immutable]:
        return generics.get_concrete_parent_arg(cls, JournalledCollection, "T_Immutable")

    @classmethod
    def get_concrete_content_type(cls) -> type[T_Value]:
        return generics.get_concrete_parent_arg(cls, JournalledCollection, "T_Value")

    @classmethod
    def __get_pydantic_core_schema__(cls, source: type[Any], handler: GetCoreSchemaHandler) -> CoreSchema:
        assert cls is source
        schema = cls.get_core_schema(source, handler)
        return core_schema.no_info_before_validator_function(
            function= cls.coerce,
            schema= schema,
            serialization=core_schema.model_ser_schema(cls.get_concrete_immutable_type(), schema),
        )

    @classmethod
    def coerce(cls, value: Any) -> T_Immutable:
        if isinstance(value, cls):
            return value.make_immutable()

        concrete = cls.get_concrete_immutable_type()
        if isinstance(value, concrete):
            return value

        return concrete(value) # pyright: ignore[reportCallIssue]

    @classmethod
    def _pydantic_serialize(cls, value: Any, info: core_schema.SerializationInfo) -> str:
        if isinstance(value, cls):
            return str(value)
        elif isinstance(value, str):
            return value
        else:
            raise TypeError(f"Expected a ConfigFilePath or string, got {type(value).__name__}")