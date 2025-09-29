# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref

from pydantic import model_validator, ConfigDict
from pydantic.fields import FieldInfo
from typing import Any, override, ClassVar, TYPE_CHECKING
from collections.abc import Sequence, Mapping, Set

from ..mixins import HierarchicalMixinMinimal, HierarchicalMutableProtocol, NamedMutableProtocol, HierarchicalProtocol, NamedProtocol

from .single_initialization import SingleInitializationModel


class HierarchicalRootModel(SingleInitializationModel, HierarchicalMixinMinimal):
    model_config = ConfigDict(
        extra='forbid',
        validate_assignment=True,
    )

    PROPAGATE_FROM_PARENT : ClassVar[bool] = True
    PROPAGATE_TO_CHILDREN : ClassVar[bool] = True
    PROPAGATE_INSTANCE_PARENT_FROM_PARENT : ClassVar[bool] = True
    PROPAGATE_INSTANCE_PARENT_TO_CHILDREN : ClassVar[bool] = True

    @property
    def instance_parent(self) -> HierarchicalProtocol | NamedProtocol | None:
        return None

    # NOTE: We use object.__setattr__ to avoid triggering Pydantic's validation which would raise an error if the object is not
    #       mutable.
    #       Since it only happens at the model validation stage as part of __init__ we are not breaking the mutability contract.
    #       We do sanity check that the current values are not already set to avoid overwriting them.
    def _seed_parent_to_object(self, *, obj : Any) -> None:
        if isinstance(obj, HierarchicalMutableProtocol) and obj.instance_parent is not self:
            if not getattr(type(obj), 'PROPAGATE_INSTANCE_PARENT_FROM_PARENT', True):
                return
            if (parent := obj.instance_parent) is not None:
                if parent is obj:
                    return

                # Entity special case
                from ...portfolio.util.versioned_uid import VersionedUid
                if isinstance(self, VersionedUid) and isinstance(parent, VersionedUid) and self.is_newer_version_than(parent):
                    pass
                else:
                    raise ValueError(f"{type(obj).__name__} {obj} already has a parent: {obj.instance_parent}. Cannot overwrite with {self}.")

            from .hierarchical import HierarchicalModel
            if isinstance(obj, HierarchicalModel):
                object.__setattr__(obj, 'instance_parent_weakref', weakref.ref(self))
            else:
                # If there is no setter, python raises AttributeError
                try:
                    object.__setattr__(obj, 'instance_parent', self)
                except AttributeError:
                    pass

    def _seed_name_to_object(self, *, obj : Any, name : str) -> None:
        if isinstance(obj, NamedMutableProtocol) and obj.instance_name != name:
            if not getattr(type(obj), 'PROPAGATE_INSTANCE_NAME_FROM_PARENT', True):
                return
            if (current := obj.instance_name) is not None:
                if current == name:
                    return
                raise ValueError(f"{type(obj).__name__} {obj} already has a name set: {obj.instance_name}. Cannot overwrite with {name}.")
            object.__setattr__(obj, 'instance_name', name)

    def _seed_parent_and_name_to_object(self, *, obj : Any, name : str, propagate_name : bool, propagate_parent : bool) -> None:
        if not getattr(type(obj), 'PROPAGATE_FROM_PARENT', True):
            return

        from ...portfolio.util.uid import Uid
        if isinstance(obj, Uid):
            from ...portfolio.models.entity import Entity
            obj = Entity.by_uid_or_none(obj)
            if obj is None:
                return

        if propagate_parent:
            self._seed_parent_to_object(obj=obj)
        if propagate_name:
            self._seed_name_to_object(obj=obj, name=name)

    def _seed_parent_and_name_to_field(self, fldnm : str, fldinfo : FieldInfo | None = None) -> None:
        if fldnm == 'instance_parent':
            return

        if fldinfo is None:
            fldinfo = type(self).model_fields[fldnm]

        extra = fldinfo.json_schema_extra if isinstance(fldinfo.json_schema_extra, dict) else None

        # Global propagation - class config
        propagate = None
        if extra:
            propagate = extra.get('propagate', None)
        if propagate is None:
            propagate = getattr(type(self), 'PROPAGATE_TO_CHILDREN', True)
        propagate = bool(propagate)
        if not propagate:
            return

        # Instance name propagation - class config
        propagate_name = None
        if extra:
            propagate_name = extra.get('propagate_name', None)
        if propagate_name is None:
            propagate_name = getattr(type(self), 'PROPAGATE_INSTANCE_NAME_TO_CHILDREN', True)
        propagate_name = bool(propagate_name)

        # Instance parent propagation - class config
        propagate_parent = None
        if extra:
            propagate_parent = extra.get('propagate_parent', None)
        if propagate_parent is None:
            propagate_parent = getattr(type(self), 'PROPAGATE_INSTANCE_PARENT_TO_CHILDREN', True)
        propagate_parent = bool(propagate_parent)

        if not propagate_name and not propagate_parent:
            return

        # Get field value
        fld = getattr(self, fldnm, None)
        if fld is None:
            return

        # Do propagation
        from ...portfolio.util.uid import Uid
        if isinstance(fld, (HierarchicalMutableProtocol, NamedMutableProtocol, Uid)):
            self._seed_parent_and_name_to_object(obj=fld, name=fldnm, propagate_name=propagate_name, propagate_parent=propagate_parent)
        elif isinstance(fld, (Sequence, Set)) and not isinstance(fld, (str, bytes, bytearray)):
            for i, item in enumerate(fld):
                self._seed_parent_and_name_to_object(obj=item, name=f"{fldnm}[{i}]", propagate_name=propagate_name, propagate_parent=propagate_parent)
        elif isinstance(fld, Mapping):
            for key, item in fld.items():
                self._seed_parent_and_name_to_object(obj=item, name=f"{fldnm}.{key}", propagate_name=propagate_name, propagate_parent=propagate_parent)


    @model_validator(mode='after')
    def _validator_seed_parent_and_name(self) -> Any:
        for fldnm, fldinfo in type(self).model_fields.items():
            self._seed_parent_and_name_to_field(fldnm, fldinfo)
        return self

    if not TYPE_CHECKING:
        @override
        def __setattr__(self, name : str, value : Any) -> None:
            super().__setattr__(name, value)

            if name in type(self).model_fields:
                self._seed_parent_and_name_to_field(name)