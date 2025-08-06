# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import rich.repr

from pydantic import BaseModel, ConfigDict, ValidationInfo, model_validator, PrivateAttr
from typing import override, Any

from ...helpers.classproperty import ClassPropertyDescriptor
from ..default import Default, DefaultFactory, DefaultDiff


class BaseConfigModel(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        ignored_types=(ClassPropertyDescriptor,)
    )


    _default_diff : DefaultDiff | None = PrivateAttr(default=None)


    @override
    def __rich_repr__(self) -> rich.repr.Result:

        for attr, info in self.__class__.model_fields.items():
            if info.repr is False:
                continue

            value = getattr(self, attr, None)
            if value is None:
                yield attr, value
                continue

            factory = info.default_factory
            if isinstance(factory, DefaultFactory):
                diff = DefaultDiff(value, factory.default)
                yield attr, diff
                continue

            yield attr, value
            continue


    @model_validator(mode='before')
    @classmethod
    def _validate_default(cls, value: Any, info : ValidationInfo) -> Any:
        # We only support default values for raw data (dictionaries)
        if not isinstance(value, dict):
            return value

        # If no context is provided, we cannot set defaults
        context = info.context or {}
        default_ctx = context.get('default', None)
        if default_ctx is None:
            return value

        # Iterate over the model fields to find DefaultFactory instances
        for attr, fldinfo in cls.model_fields.items():
            factory = fldinfo.default_factory
            if not isinstance(factory, DefaultFactory):
                continue

            # Obtain the default value from context
            default_obj = factory.get_scope(default_ctx)

            ## Merge the default values into the model
            attr_value = value.get(attr, None)
            if attr_value is None:
                attr_value = default_obj
                value[attr] = attr_value
            else:
                for key, val in default_obj.model_fields.items():
                    if key not in attr_value:
                        if val.default_factory is not None:
                            new_value = val.default_factory()
                        else:
                            new_value = val.default
                        attr_value[key] = new_value

        return value




