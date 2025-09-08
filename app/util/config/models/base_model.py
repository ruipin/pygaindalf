# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import rich.repr

from pydantic import ConfigDict, ModelWrapValidatorHandler, ValidationInfo, model_validator, Field, field_validator
from typing import override, Any

from ...mixins.models import LoggableHierarchicalNamedModel

from ...helpers.classproperty import ClassPropertyDescriptor
from ..inherit import InheritFactory, Inherit, Default

from ..context_stack import ContextStack




class BaseConfigModel(LoggableHierarchicalNamedModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
    )


    inherited : Inherit | None = Field(default=None, repr=False)
    defaulted : Default | None = Field(default=None, repr=False)


    @override
    def __rich_repr__(self) -> rich.repr.Result:
        for attr, info in self.__class__.model_fields.items():
            if info.repr is False:
                continue

            if self.inherited is not None and attr in self.inherited:
                continue
            if self.defaulted is not None and attr in self.defaulted:
                continue

            value = getattr(self, attr, None)
            if value is None:
                yield attr, value
                continue

            yield attr, value
            continue

        if self.inherited is not None:
            yield self.inherited
        if self.defaulted is not None:
            yield self.defaulted


    @model_validator(mode='wrap')
    @classmethod
    def _validator_model_propagate_context(cls, value: Any, handler: ModelWrapValidatorHandler, info : ValidationInfo) -> Any:
        """
        Propagate the context from the model to the field values.
        This allows fields to access the context when they are validated.
        """
        # If the value is not a dictionary, we cannot propagate context
        if not isinstance(value, dict):
            return handler(value)

        # Create a new context with the current value
        with ContextStack.with_context(value):
            return handler(value)

    @field_validator('*', mode='wrap')
    @classmethod
    def _validator_field_propagate_context(cls, value: Any, handler: ModelWrapValidatorHandler, info : ValidationInfo) -> Any:
        """
        Propagate the context from the model to the field values.
        This allows fields to access the context when they are validated.
        """
        # If the value is not a dictionary, we cannot propagate context
        if not isinstance(value, dict):
            return handler(value)

        name = info.field_name
        if name is None:
            #cls.log.warning("Field name is None, cannot propagate context") # TODO: This seems to have broken in pydantic 2.12.0a1
            return handler(value)

        # Create a new context with the current value
        with ContextStack.with_updated_name(name):
            return handler(value)


    @model_validator(mode='before')
    @classmethod
    def _validator_inherit(cls, value: Any, info : ValidationInfo) -> Any:
        if not isinstance(value, dict):
            return value

        inherited = []
        defaulted = []

        for fld, fldinfo in cls.model_fields.items():
            if fld in value:
                continue

            factory = fldinfo.default_factory
            if isinstance(factory, InheritFactory):
                inherit = factory.search(fld)
                if inherit is None:
                    defaulted.append(fld)
                    continue
                cls.log.debug(t"Field '{fld}' has InheritFactory, found value: {inherit}")
                value[fld] = inherit
                inherited.append(fld)

        if inherited:
            value['inherited'] = Inherit(inherited)

        if not ContextStack.find_name('default') and defaulted:
            value['defaulted'] = Default(defaulted)

        return value