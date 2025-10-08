# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from collections.abc import Generator, Mapping
from typing import Any, dataclass_transform

from frozendict import frozendict
from pydantic import Field

from ....util.helpers import type_hints


@dataclass_transform(kw_only_default=True, field_specifiers=(Field,))
class EntitySchemaBase:
    def get_schema_field_annotations(self) -> Mapping[str, Any]:
        for mro in reversed(self.__class__.__mro__):
            if mro is EntitySchemaBase:
                continue
            if not issubclass(mro, EntitySchemaBase):
                continue

            break
        else:
            msg = "Class does not inherit from EntitySchemaBase"
            raise RuntimeError(msg)

        return type_hints.get_type_hints(mro)

    def iter_schema_field_values(self) -> Generator[tuple[str, Any]]:
        annotations = self.get_schema_field_annotations()
        for key in annotations:
            yield key, getattr(self, key)

    def get_schema_field_values(self) -> Mapping[str, Any]:
        return frozendict(self.iter_schema_field_values())
