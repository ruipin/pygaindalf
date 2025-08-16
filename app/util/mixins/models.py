# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import warnings

from pydantic import BaseModel, model_validator, Field, field_validator
from typing import Any, Self, Annotated

from . import HierarchicalMutableProtocol, NamedMutableProtocol, HierarchicalMixinMinimal, NamedMixinMinimal, LoggableMixin, HierarchicalProtocol, NamedProtocol



class HierarchicalModel(BaseModel, HierarchicalMixinMinimal):
    instance_parent : object | None = Field(default=None, repr=False, exclude=True, description="Parent of this instance in the hierarchy. Can be None if this is a root instance.")

    @field_validator('instance_parent', mode='after')
    @classmethod
    def _validate_instance_parent(cls, obj : object | None) -> HierarchicalProtocol | NamedProtocol | None:
        if obj is not None and not isinstance(obj, (HierarchicalProtocol | NamedProtocol)):
            raise TypeError(f"Expected HierarchicalProtocol | NamedProtocol | None, got {type(obj)}")
        return obj

    # NOTE: We use object.__setattr__ to avoid triggering Pydantic's validation which would raise an error if the object is not
    #       mutable.
    #       Since it only happens at the model validation stage as part of __init__ we are not breaking the mutability contract.
    #       We do sanity check that the current values are not already set to avoid overwriting them.
    def _seed_parent_to_object(self, obj : Any) -> None:
        if isinstance(obj, HierarchicalMutableProtocol) and obj.instance_parent is not self:
            if obj.instance_parent is not None:
                raise ValueError(f"Object {obj} already has a parent set: {obj.instance_parent}. Cannot overwrite with {self}.")
            object.__setattr__(obj, 'instance_parent', self)

    def _seed_name_to_object(self, obj : Any, name : str) -> None:
        if isinstance(obj, NamedMutableProtocol) and obj.instance_name != name:
            if obj.instance_name is not None:
                raise ValueError(f"Object {obj} already has a name set: {obj.instance_name}. Cannot overwrite with {name}.")
            object.__setattr__(obj, 'instance_name', name)

    def _seed_parent_and_name_to_object(self, obj : Any, name : str) -> None:
        self._seed_parent_to_object(obj)
        self._seed_name_to_object(obj, name)

    @model_validator(mode='after')
    def _validator_seed_parent_and_name(self) -> Any:
        for fldnm, fldinfo in self.__class__.model_fields.items():
            fld = getattr(self, fldnm, None)
            if fld is None:
                continue

            extra = fldinfo.json_schema_extra if isinstance(fldinfo.json_schema_extra, dict) else None
            hierarchical = extra.get('hierarchical', True) if extra else True
            if not hierarchical:
                continue

            if isinstance(fld, list):
                for item in fld:
                    self._seed_parent_and_name_to_object(item, fldnm)
            elif isinstance(fld, dict):
                for key, item in fld.items():
                    self._seed_parent_and_name_to_object(item, f"{fldnm}.{key}")
            else:
                self._seed_parent_and_name_to_object(fldnm, fld)

        return self

class HierarchicalNamedModel(HierarchicalModel):
    instance_name : str | None = Field(default=None, min_length=1, description="Name of the instance.")

class LoggableHierarchicalModel(LoggableMixin, HierarchicalModel):
    pass

class LoggableHierarchicalNamedModel(LoggableMixin, HierarchicalNamedModel):
    pass