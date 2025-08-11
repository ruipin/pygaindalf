# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import rich.repr

from pydantic import BaseModel, ConfigDict, ModelWrapValidatorHandler, ValidationInfo, model_validator, Field, field_validator
from typing import override, Any

from app.util.mixins import LoggableHierarchicalNamedMixin, HierarchicalMixin, NamedMixin

from ...helpers.classproperty import ClassPropertyDescriptor
from ..inherit import InheritFactory, Inherit, Default

from ..context_stack import ContextStack




class BaseConfigModel(BaseModel, LoggableHierarchicalNamedMixin):
    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        ignored_types=(ClassPropertyDescriptor,)
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


    def _seed_parent_and_name_to_object(self, name : str, obj : Any) -> None:
        if isinstance(obj, HierarchicalMixin):
            obj._set_instance_parent(self)
        if isinstance(obj, NamedMixin):
            obj._set_instance_name(name)

    @model_validator(mode='after')
    def _validator_seed_parent_and_name(self, info: ValidationInfo) -> Any:
        for fldnm in self.__class__.model_fields.keys():
            fld = getattr(self, fldnm, None)
            if fld is None:
                continue

            if isinstance(fld, list):
                for item in fld:
                    self._seed_parent_and_name_to_object(fldnm, item)
            elif isinstance(fld, dict):
                for key, item in fld.items():
                    self._seed_parent_and_name_to_object(f"{fldnm}.{key}", item)
            else:
                self._seed_parent_and_name_to_object(fldnm, fld)

        return self


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
    def _validator_propagate_context(cls, value: Any, handler: ModelWrapValidatorHandler, info : ValidationInfo) -> Any:
        """
        Propagate the context from the model to the field values.
        This allows fields to access the context when they are validated.
        """
        # If the value is not a dictionary, we cannot propagate context
        if not isinstance(value, dict):
            return handler(value)

        name = info.field_name
        if name is None:
            cls.log.warning("Field name is None, cannot propagate context")
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
                cls.log.debug(f"Field '{fld}' has InheritFactory, found value: {inherit}")
                value[fld] = inherit
                inherited.append(fld)

        if inherited:
            value['inherited'] = Inherit(inherited)

        if not ContextStack.find_name('default') and defaulted:
            value['defaulted'] = Default(defaulted)

        return value