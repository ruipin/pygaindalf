# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import typing
import pydantic

from frozendict import frozendict
from pydantic_core import core_schema as core_schema


class _PydanticFrozenDictAnnotation:
	@classmethod
	def __get_pydantic_core_schema__(
		cls, source_type: typing.Any, handler: pydantic.GetCoreSchemaHandler
	) -> core_schema.CoreSchema:
		def validate_from_dict[_K, _V](d: dict[_K, _V] | frozendict[_K, _V]) -> frozendict[_K, _V]:
			return frozendict[_K, _V](d)

		frozendict_schema = core_schema.chain_schema(
			[
				handler.generate_schema(dict[*typing.get_args(source_type)]), # pyright: ignore[reportInvalidTypeArguments] since pyright is simply wrong here
				core_schema.no_info_plain_validator_function(validate_from_dict),
				core_schema.is_instance_schema(frozendict),
			]
		)
		return core_schema.json_or_python_schema(
			json_schema=frozendict_schema,
			python_schema=frozendict_schema,
			serialization=core_schema.plain_serializer_function_ser_schema(dict),
		)


_K = typing.TypeVar('_K')
_V = typing.TypeVar('_V')
FrozenDict = typing.Annotated[frozendict[_K, _V], _PydanticFrozenDictAnnotation]