# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import warnings

from pydantic import BaseModel, model_validator, Field, field_validator, PrivateAttr, ConfigDict
from pydantic.fields import FieldInfo
from typing import Any, Self, Annotated, override, ClassVar, final, TYPE_CHECKING

from ..helpers.callguard import CallguardedModelMixin

from . import HierarchicalMutableProtocol, NamedMutableProtocol, HierarchicalMixinMinimal, NamedMixinMinimal, LoggableMixin, HierarchicalProtocol, NamedProtocol


class SingleInitializationModel(CallguardedModelMixin, BaseModel):
    __initialized : bool = PrivateAttr(default=False)

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        instance.__initialized = False
        return instance

    def __init__(self, *args, **kwargs):
        if self.initialized:
            raise RuntimeError(f"Model {self} is already initialized.")

        super().__init__(*args, **kwargs)
        self.__initialized = True

    @override
    def model_post_init(self, context : Any) -> None:
        super().model_post_init(context)

    @final
    @property
    def initialized(self) -> bool:
        return self.__initialized


class HierarchicalModel(SingleInitializationModel, HierarchicalMixinMinimal):
    PROPAGATE_FROM_PARENT : ClassVar[bool] = True
    PROPAGATE_TO_CHILDREN : ClassVar[bool] = True
    PROPAGATE_INSTANCE_PARENT_FROM_PARENT : ClassVar[bool] = True
    PROPAGATE_INSTANCE_PARENT_TO_CHILDREN : ClassVar[bool] = True

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
    def _seed_parent_to_object(self, *, obj : Any) -> None:
        if isinstance(obj, HierarchicalMutableProtocol) and obj.instance_parent is not self:
            if not getattr(obj.__class__, 'PROPAGATE_INSTANCE_PARENT_FROM_PARENT', True):
                return
            if (parent := obj.instance_parent) is not None:
                if parent is obj:
                    return
                #if (uid := getattr(self, 'uid', None)) is None or (parent_uid := getattr(parent, 'uid', None)) is None or uid != parent_uid:
                raise ValueError(f"Object {obj} already has a parent set: {obj.instance_parent}. Cannot overwrite with {self}.")
            object.__setattr__(obj, 'instance_parent', self)

    def _seed_name_to_object(self, *, obj : Any, name : str) -> None:
        if isinstance(obj, NamedMutableProtocol) and obj.instance_name != name:
            if not getattr(obj.__class__, 'PROPAGATE_INSTANCE_NAME_FROM_PARENT', True):
                return
            if (current := obj.instance_name) is not None:
                if current == name:
                    return
                raise ValueError(f"Object {obj} already has a name set: {obj.instance_name}. Cannot overwrite with {name}.")
            object.__setattr__(obj, 'instance_name', name)

    def _seed_parent_and_name_to_object(self, *, obj : Any, name : str, propagate_name : bool, propagate_parent : bool) -> None:
        if not getattr(obj.__class__, 'PROPAGATE_FROM_PARENT', True):
            return
        if propagate_parent:
            self._seed_parent_to_object(obj=obj)
        if propagate_name:
            self._seed_name_to_object(obj=obj, name=name)

    def _seed_parent_and_name_to_field(self, fldnm : str, fldinfo : FieldInfo | None = None) -> None:
        if fldnm == 'instance_parent':
            return

        if fldinfo is None:
            fldinfo = self.__class__.model_fields[fldnm]

        extra = fldinfo.json_schema_extra if isinstance(fldinfo.json_schema_extra, dict) else None

        # Global propagation - class config
        propagate = None
        if extra:
            propagate = extra.get('propagate', None)
        if propagate is None:
            propagate = getattr(self.__class__, 'PROPAGATE_TO_CHILDREN', True)
        propagate = bool(propagate)
        if not propagate:
            return

        # Instance name propagation - class config
        propagate_name = None
        if extra:
            propagate_name = extra.get('propagate_name', None)
        if propagate_name is None:
            propagate_name = getattr(self.__class__, 'PROPAGATE_INSTANCE_NAME_TO_CHILDREN', True)
        propagate_name = bool(propagate_name)

        # Instance parent propagation - class config
        propagate_parent = None
        if extra:
            propagate_parent = extra.get('propagate_parent', None)
        if propagate_parent is None:
            propagate_parent = getattr(self.__class__, 'PROPAGATE_INSTANCE_PARENT_TO_CHILDREN', True)
        propagate_parent = bool(propagate_parent)

        if not propagate_name and not propagate_parent:
            return

        # Get field value
        fld = getattr(self, fldnm, None)
        if fld is None:
            return

        # Do propagation
        if isinstance(fld, list):
            for i, item in enumerate(fld):
                self._seed_parent_and_name_to_object(obj=item, name=f"{fldnm}[{i}]", propagate_name=propagate_name, propagate_parent=propagate_parent)
        elif isinstance(fld, dict):
            for key, item in fld.items():
                self._seed_parent_and_name_to_object(obj=item, name=f"{fldnm}.{key}", propagate_name=propagate_name, propagate_parent=propagate_parent)
        else:
            self._seed_parent_and_name_to_object(obj=fld, name=fldnm, propagate_name=propagate_name, propagate_parent=propagate_parent)

    @model_validator(mode='after')
    def _validator_seed_parent_and_name(self) -> Any:
        for fldnm, fldinfo in self.__class__.model_fields.items():
            self._seed_parent_and_name_to_field(fldnm, fldinfo)

        return self

    if not TYPE_CHECKING:
        @override
        def __setattr__(self, name : str, value : Any) -> None:
            super().__setattr__(name, value)

            if name in self.__class__.model_fields:
                self._seed_parent_and_name_to_field(name)

    @override
    def __str__(self):
        return super(HierarchicalMixinMinimal, self).__str__()

    @override
    def __repr__(self):
        return super(HierarchicalMixinMinimal, self).__repr__()

class HierarchicalNamedModel(HierarchicalModel):
    PROPAGATE_INSTANCE_NAME_FROM_PARENT : ClassVar[bool] = True
    PROPAGATE_INSTANCE_NAME_TO_CHILDREN : ClassVar[bool] = True

    instance_name : str | None = Field(default=None, min_length=1, description="Name of the instance.")

class LoggableHierarchicalModel(LoggableMixin, HierarchicalModel):
    pass

class LoggableHierarchicalNamedModel(LoggableMixin, HierarchicalNamedModel):
    pass