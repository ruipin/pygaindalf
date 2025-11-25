# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import typing

from frozendict import frozendict
from pydantic_core import core_schema


if typing.TYPE_CHECKING:
    import pydantic
    import rich.repr


# Add pydantic support for frozendict
class PydanticFrozenDictAnnotation:
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: typing.Any, handler: pydantic.GetCoreSchemaHandler) -> core_schema.CoreSchema:
        def validate_from_dict[K, V](d: dict[K, V] | frozendict[K, V]) -> frozendict[K, V]:
            return frozendict[K, V](d)

        frozendict_schema = core_schema.chain_schema(
            [
                handler.generate_schema(dict[*typing.get_args(source_type)]),  # pyright: ignore[reportInvalidTypeArguments] since pyright is simply wrong here
                core_schema.no_info_plain_validator_function(validate_from_dict),
                core_schema.is_instance_schema(frozendict),
            ]
        )
        return core_schema.json_or_python_schema(
            json_schema=frozendict_schema,
            python_schema=frozendict_schema,
            serialization=core_schema.plain_serializer_function_ser_schema(dict),
        )


_K = typing.TypeVar("_K")
_V = typing.TypeVar("_V")
FrozenDict = typing.Annotated[frozendict[_K, _V], PydanticFrozenDictAnnotation]


# Add rich repr support to frozendict
def frozendict_rich_repr(self: frozendict) -> rich.repr.Result:
    for key, value in self.items():
        yield str(key), value


frozendict.__rich_repr__ = frozendict_rich_repr  # pyright: ignore[reportAttributeAccessIssue]
