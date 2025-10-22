# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from collections.abc import Generator, Mapping
from collections.abc import Set as AbstractSet
from typing import Any, ClassVar, NotRequired, TypedDict, Unpack, dataclass_transform, get_origin

from frozendict import frozendict
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

from ....util.helpers import type_hints


class IterSchemaFieldOptions(TypedDict):
    by_alias: NotRequired[bool]
    recursive: NotRequired[bool]
    private: NotRequired[bool]
    class_vars: NotRequired[bool]
    skip: NotRequired[AbstractSet[str]]


@dataclass_transform(kw_only_default=True, field_specifiers=(Field,))
class EntitySchemaBase:
    def get_schema_field_annotations(self, *, recursive: bool = True) -> Mapping[str, Any]:
        hints = {}
        found = False

        for mro in reversed(self.__class__.__mro__):
            if mro is EntitySchemaBase:
                continue
            if not issubclass(mro, EntitySchemaBase):
                continue
            if issubclass(mro, BaseModel):
                continue

            found = True

            _hints = type_hints.get_type_hints(mro)
            if not recursive:
                return _hints
            else:
                hints.update(_hints)

        if not found:
            msg = "Class does not inherit from EntitySchemaBase"
            raise RuntimeError(msg)

        return frozendict(hints)

    def iter_schema_field_values(self, **options: Unpack[IterSchemaFieldOptions]) -> Generator[tuple[str, Any]]:
        by_alias = options.get("by_alias", True)
        recursive = options.get("recursive", True)
        private = options.get("private", False)
        class_vars = options.get("class_vars", False)
        skip = options.get("skip")

        annotations = self.get_schema_field_annotations(recursive=recursive)
        for key in annotations:
            annotation = annotations[key]
            if not class_vars and get_origin(annotation) is ClassVar:
                continue

            val = getattr(self, key, None)
            if by_alias:
                fld = getattr(type(self), key, None)
                if isinstance(fld, FieldInfo) and fld.alias is not None:
                    key = fld.alias

            if not private and key.startswith("_"):
                continue
            if skip and key in skip:
                continue

            yield key, val

    def get_schema_field_values(self, **options: Unpack[IterSchemaFieldOptions]) -> Mapping[str, Any]:
        return frozendict(self.iter_schema_field_values(**options))
