# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from pydantic import BaseModel, model_validator
from typing import Any

from . import HierarchicalMutableProtocol, NamedMutableProtocol, HierarchicalMixin, NamedMixin, LoggableMixin, HierarchicalProtocol, NamedProtocol



class HierarchicalModel(BaseModel, HierarchicalMixin):
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
            if not obj.is_instance_name_default():
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

class HierarchicalNamedModel(HierarchicalModel, NamedMixin):
    def __init__(self, instance_name : str | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if instance_name is not None:
            self.instance_name = instance_name

class LoggableHierarchicalModel(LoggableMixin, HierarchicalModel):
    def __init__(self, instance_parent : HierarchicalProtocol | NamedProtocol | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if instance_parent is not None:
            self.instance_parent = instance_parent

class LoggableHierarchicalNamedModel(LoggableMixin, HierarchicalNamedModel):
    pass