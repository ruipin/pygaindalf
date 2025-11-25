# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref

import pytest

from pydantic import BaseModel, Field

from app.util.mixins import NamedMixin
from app.util.models.hierarchical import HierarchicalModel
from app.util.models.hierarchical_root import HierarchicalRootModel


class ChildHierModel(HierarchicalModel, NamedMixin):
    value: int = 0


class RootWithSingleChild(HierarchicalRootModel):
    child: ChildHierModel | None = None


class RootWithListChildren(HierarchicalRootModel):
    children: list[ChildHierModel] = Field(default_factory=list)


class RootWithDictChildren(HierarchicalRootModel):
    children: dict[str, ChildHierModel] = Field(default_factory=dict)


class RootNonPropagate(HierarchicalRootModel):
    PROPAGATE_TO_CHILDREN = False
    child: ChildHierModel | None = None


class SimpleHierarchicalRoot(HierarchicalRootModel):
    x: int = 0


@pytest.mark.model
@pytest.mark.hierarchical_model
class TestHierarchicalRootModelBasics:
    def test_root_instance_parent_is_none(self) -> None:
        root = SimpleHierarchicalRoot(x=1)
        assert root.instance_parent is None

    def test_str_and_repr_dispatch_to_hierarchical_mixin(self) -> None:
        root = SimpleHierarchicalRoot(x=2)
        s = str(root)
        r = repr(root)
        # Smoke tests: ensure they are non-empty and include class name
        assert "SimpleHierarchicalRoot" in s
        assert "SimpleHierarchicalRoot" in r


@pytest.mark.model
@pytest.mark.hierarchical_model
class TestParentPropagationSingleChild:
    def test_seed_parent_and_name_single_child_on_init(self) -> None:
        child = ChildHierModel(value=1)
        root = RootWithSingleChild(child=child)

        # Parent should be weakref to root
        assert child.instance_parent is root
        assert child.instance_parent_field_name == "child"
        assert child.instance_parent_field_key is None
        assert isinstance(child.instance_parent_weakref, weakref.ref)

        # Name propagation
        assert child.instance_name == "child"

    def test_seed_parent_and_name_single_child_on_setattr(self) -> None:
        root = RootWithSingleChild()
        child = ChildHierModel(value=2)

        root.child = child

        assert child.instance_parent is root
        assert child.instance_parent_field_name == "child"
        assert child.instance_parent_field_key is None
        assert child.instance_name == "child"


@pytest.mark.model
@pytest.mark.hierarchical_model
class TestParentPropagationCollections:
    def test_list_children_parent_and_name(self) -> None:
        a = ChildHierModel(value=1)
        b = ChildHierModel(value=2)
        root = RootWithListChildren(children=[a, b])

        assert a.instance_parent is root
        assert a.instance_parent_field_name == "children"
        assert a.instance_parent_field_key == 0
        assert a.instance_name == "children[0]"

        assert b.instance_parent is root
        assert b.instance_parent_field_name == "children"
        assert b.instance_parent_field_key == 1
        assert b.instance_name == "children[1]"

    def test_dict_children_parent_and_name(self) -> None:
        a = ChildHierModel(value=1)
        b = ChildHierModel(value=2)
        root = RootWithDictChildren(children={"a": a, "b": b})

        assert a.instance_parent is root
        assert a.instance_parent_field_name == "children"
        assert a.instance_parent_field_key == "a"
        assert a.instance_name == "children[a]"

        assert b.instance_parent is root
        assert b.instance_parent_field_name == "children"
        assert b.instance_parent_field_key == "b"
        assert b.instance_name == "children[b]"


@pytest.mark.model
@pytest.mark.hierarchical_model
class TestPropagationControls:
    def test_no_propagation_when_class_flag_disabled(self) -> None:
        child = ChildHierModel(value=1)
        RootNonPropagate(child=child)

        # No parent or name should be propagated
        assert child.instance_parent is None
        assert child.instance_parent_field_name is None
        assert child.instance_parent_field_key is None
        assert child.instance_name is None


@pytest.mark.model
@pytest.mark.hierarchical_model
class TestHierarchicalModelHelpers:
    def test_clear_instance_parent_data(self) -> None:
        child = ChildHierModel(value=1)
        root = RootWithSingleChild(child=child)

        assert child.instance_parent is root
        assert child.instance_parent_field_name == "child"

        child._clear_instance_parent_data()

        assert child.instance_parent is None
        assert child.instance_parent_field_name is None
        assert child.instance_parent_field_key is None

    def test_previous_property_for_sequence_parent(self) -> None:
        a = ChildHierModel(value=1)
        b = ChildHierModel(value=2)
        c = ChildHierModel(value=3)
        root = RootWithListChildren(children=[a, b, c])

        assert b.previous is a
        assert c.previous is b
        assert a.instance_parent is root
        assert b.instance_parent is root
        assert c.instance_parent is root

    def test_previous_is_none_for_first_or_missing_parent(self) -> None:
        a = ChildHierModel(value=1)
        root = RootWithListChildren(children=[a])

        # First element has no previous
        assert a.previous is None
        assert a.instance_parent is root

        # Child detached from parent has no collection context
        orphan = ChildHierModel(value=2)
        assert orphan.previous is None

    def test_instance_parent_validator_accepts_none_and_weakref(self) -> None:
        # Re-run validator via model copy with new parent weakref
        new_root = RootWithSingleChild()
        ref = weakref.ref(new_root)
        child2 = ChildHierModel.model_validate({"value": 2, "instance_parent": ref})
        assert child2.instance_parent is new_root

    def test_instance_parent_validator_rejects_invalid_type(self) -> None:
        with pytest.raises(TypeError):
            ChildHierModel.model_validate({"value": 1, "instance_parent": 123})


@pytest.mark.model
@pytest.mark.hierarchical_model
class TestHierarchicalRootModelSeedParentPrivate:
    def test_seed_parent_when_not_mutable(self) -> None:
        class NonHierChild(BaseModel):
            instance_parent: object | None = None

        class RootWithNonHierChild(HierarchicalRootModel):
            child: NonHierChild | None = None

        child = NonHierChild()
        root = RootWithNonHierChild(child=child)

        # HierarchicalRootModel uses object.__setattr__ on attribute if present
        assert child.instance_parent is root
