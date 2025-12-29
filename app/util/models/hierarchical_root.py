# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import contextlib
import weakref

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, Any, ClassVar, override

from pydantic import ConfigDict, model_validator
from pydantic.fields import FieldInfo

from ..helpers import script_info
from ..mixins import HierarchicalMixinMinimal, InstanceParentMutableProtocol, NamedMutableProtocol, ParentType
from .annotated import is_non_child_type
from .single_initialization import SingleInitializationModel
from .superseded import SupersededProtocol
from .uid import Uid


class HierarchicalRootModel(SingleInitializationModel, HierarchicalMixinMinimal):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_by_alias=True,
        serialize_by_alias=True,
    )

    # These class variables can be overridden in subclasses to control propagation behavior
    # This includes propagating instance parents and names
    PROPAGATE_FROM_PARENT: ClassVar[bool] = True  # Whether to propagate information to an instance of this model
    PROPAGATE_TO_CHILDREN: ClassVar[bool] = True  # Whether to propagating from an instance of this model to its children
    PROPAGATE_INSTANCE_PARENT_FROM_PARENT: ClassVar[bool] = True  # Whether to propagate a parent to an instance of this model
    PROPAGATE_INSTANCE_PARENT_TO_CHILDREN: ClassVar[bool] = True  # Whether to propagate an instance of this model as the parent to its children
    PROPAGATE_INSTANCE_PARENT_FROM_PARENT_TO_CHILDREN: ClassVar[bool] = (
        False  # Whether to propagate the model's parent to its children, instead of propagating itself.
    )

    @property
    def instance_parent(self) -> ParentType | None:
        return None

    # NOTE: We use object.__setattr__ to avoid triggering Pydantic's validation which would raise an error if the object is not
    #       mutable.
    #       Since it only happens at the model validation stage as part of __init__ we are not breaking the mutability contract.
    #       We do sanity check that the current values are not already set to avoid overwriting them.
    def _seed_parent_to_object(self, *, obj: Any, fldnm: str, fldkey: Any) -> None:
        if isinstance(obj, InstanceParentMutableProtocol):
            if not getattr(type(obj), "PROPAGATE_INSTANCE_PARENT_FROM_PARENT", True):
                return
            propagate_parent = self if not getattr(type(self), "PROPAGATE_INSTANCE_PARENT_FROM_PARENT_TO_CHILDREN", False) else self.instance_parent
            current = obj.instance_parent
            already_propagated = current is propagate_parent
            if current is not None and not already_propagated:
                msg = f"{type(obj).__name__} {obj} already has a parent: {current}. Cannot overwrite with {propagate_parent}."
                raise ValueError(msg)

            from .hierarchical import HierarchicalModel

            if isinstance(obj, HierarchicalModel):
                if script_info.enable_extra_sanity_checks():
                    fld = getattr(self, fldnm, None)
                    assert fld is not None, "Inconsistent state when propagating parent to child."
                    if fldkey is None:
                        assert fld is obj, "Inconsistent state when propagating parent to child."
                    elif isinstance(fld, Mapping):
                        assert fld.get(fldkey, None) is obj, "Inconsistent state when propagating parent to child."
                    elif isinstance(fld, Sequence):
                        assert fld[fldkey] is obj, "Inconsistent state when propagating parent to child."

                if not already_propagated:
                    object.__setattr__(obj, "instance_parent_weakref", weakref.ref(propagate_parent))
                # We still propagate the field/key in case those have changed
                object.__setattr__(obj, "instance_parent_field_name", fldnm)
                object.__setattr__(
                    obj, "instance_parent_field_key_weakref", fldkey if fldkey is None or isinstance(fldkey, (int, str)) else weakref.ref(fldkey)
                )
            else:
                if already_propagated:
                    return
                # If there is no setter, python raises AttributeError
                with contextlib.suppress(AttributeError):
                    object.__setattr__(obj, "instance_parent", propagate_parent)

    def _seed_name_to_object(self, *, obj: Any, name: str) -> None:
        if isinstance(obj, NamedMutableProtocol) and obj.instance_name != name:
            if not getattr(type(obj), "PROPAGATE_INSTANCE_NAME_FROM_PARENT", True):
                return
            if (current := obj.instance_name) is not None:
                return
                if current == name:
                    return
                msg = f"{type(obj).__name__} {obj} already has a name set: {obj.instance_name}. Cannot overwrite with {name}."
                raise ValueError(msg)
            object.__setattr__(obj, "instance_name", name)

    def _seed_parent_and_name_to_object(self, *, obj: Any, fldnm: str, fldkey: Any, propagate_name: bool, propagate_parent: bool) -> None:
        if not getattr(type(obj), "PROPAGATE_FROM_PARENT", True):
            return

        if isinstance(obj, Uid):
            from ...portfolio.models.entity import Entity

            obj = Entity.by_uid_or_none(obj)
            if obj is None or obj is self:
                return

        if propagate_parent:
            self._seed_parent_to_object(obj=obj, fldnm=fldnm, fldkey=fldkey)
        if propagate_name:
            name = f"{fldnm}[{fldkey}]" if isinstance(fldkey, (str, int)) else fldnm
            self._seed_name_to_object(obj=obj, name=name)

    def _should_seed_parent_and_name_to_field(self, fldnm: str, fldinfo: FieldInfo | None = None) -> tuple[bool, bool]:
        from .hierarchical import HierarchicalModel

        if bool(fldnm in ("uid", "instance_name") or fldnm in HierarchicalModel.INSTANCE_PARENT_FIELD_NAMES):
            return (False, False)

        if fldinfo is None:
            fldinfo = type(self).model_fields[fldnm]

        extra = fldinfo.json_schema_extra if isinstance(fldinfo.json_schema_extra, dict) else None

        # We only propagate to children
        if extra and (is_child := extra.get("child", None)) is not None:
            if not is_child:
                return (False, False)
        elif (ann := fldinfo.annotation) is not None and is_non_child_type(ann):
            return (False, False)

        # Global propagation - class config
        propagate = None
        if extra:
            propagate = extra.get("propagate", None)
        if propagate is None:
            propagate = getattr(type(self), "PROPAGATE_TO_CHILDREN", True)
        propagate = bool(propagate)
        if not propagate:
            return (False, False)

        # Instance name propagation - class config
        propagate_name = None
        if extra:
            propagate_name = extra.get("propagate_name", None)
        if propagate_name is None:
            propagate_name = getattr(type(self), "PROPAGATE_INSTANCE_NAME_TO_CHILDREN", True)
        propagate_name = bool(propagate_name)

        # Instance parent propagation - class config
        propagate_parent = None
        if extra:
            propagate_parent = extra.get("propagate_parent", None)
        if propagate_parent is None:
            propagate_parent = getattr(type(self), "PROPAGATE_INSTANCE_PARENT_TO_CHILDREN", True)
        propagate_parent = bool(propagate_parent)

        return (propagate_name, propagate_parent)

    def _seed_parent_and_name_to_field(self, fldnm: str, fldinfo: FieldInfo | None = None) -> None:
        (propagate_name, propagate_parent) = self._should_seed_parent_and_name_to_field(fldnm, fldinfo)
        if not propagate_name and not propagate_parent:
            return

        # Get field value
        fld = getattr(self, fldnm, None)
        if fld is None:
            return

        # Do propagation
        from .uid import Uid

        if isinstance(fld, (InstanceParentMutableProtocol, NamedMutableProtocol, Uid)):
            self._seed_parent_and_name_to_object(obj=fld, fldnm=fldnm, fldkey=None, propagate_name=propagate_name, propagate_parent=propagate_parent)
        elif isinstance(fld, (Sequence, AbstractSet)) and not isinstance(fld, (str, bytes, bytearray)):
            for i, item in enumerate(fld):
                self._seed_parent_and_name_to_object(obj=item, fldnm=fldnm, fldkey=i, propagate_name=propagate_name, propagate_parent=propagate_parent)
        elif isinstance(fld, Mapping):
            for key, item in fld.items():
                self._seed_parent_and_name_to_object(obj=item, fldnm=fldnm, fldkey=key, propagate_name=propagate_name, propagate_parent=propagate_parent)

    @model_validator(mode="after")
    def _validator_seed_parent_and_name(self) -> Any:
        if not isinstance(self, SupersededProtocol) or not self.superseded:
            for fldnm, fldinfo in type(self).model_fields.items():
                self._seed_parent_and_name_to_field(fldnm, fldinfo)

        return self

    if not TYPE_CHECKING:

        @override
        def __setattr__(self, name: str, value: Any) -> None:
            super().__setattr__(name, value)
            if name in type(self).model_fields:
                self._seed_parent_and_name_to_field(name)

    @override
    def __str__(self) -> str:
        return super(HierarchicalMixinMinimal, self).__str__()

    @override
    def __repr__(self) -> str:
        return super(HierarchicalMixinMinimal, self).__repr__()
