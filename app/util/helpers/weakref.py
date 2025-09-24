# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import typing, types
import pydantic
import weakref

from pydantic_core import core_schema as core_schema


class PydanticWeakrefAnnotation:
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: typing.Any, handler: pydantic.GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        def validate(obj: _T | weakref.ref[_T]) -> weakref.ref[_T]:
            return weakref.ref(obj) if not isinstance(obj, weakref.ref) else obj

        return core_schema.no_info_plain_validator_function(
            function= validate,
        )


_T = typing.TypeVar('_T')
WeakRef = typing.Annotated[weakref.ref[_T], PydanticWeakrefAnnotation]