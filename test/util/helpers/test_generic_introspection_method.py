# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import typing

import pytest

from app.util.helpers.generics import GenericIntrospectionMethod, GenericsError


# Simple domain types at module scope so they are visible inside nested class bodies
class Animal: ...


class Dog(Animal): ...


type ListAlias = list[int]
type NumberAlias = int | str
type IntAlias = int


@pytest.mark.helpers
@pytest.mark.generics
class TestGenericIntrospectionMethod:
    # Base with descriptor shortcuts for introspection
    class Parent[T]:
        # Returns the concrete specialization of T
        kind = GenericIntrospectionMethod[T]()
        # Returns the origin of the specialization (e.g., list for list[int])
        kind_origin = GenericIntrospectionMethod[T](origin=True)
        # Enforces an additional bound via descriptor argument
        kind_animal = GenericIntrospectionMethod[T](bound=Animal)

    # Specializations
    class ChildInt(Parent[int]):
        pass

    class ChildList(Parent[list[int]]):
        pass

    class ChildDog(Parent[Dog]):
        pass

    class ChildInvalid(Parent[int]):  # violates Animal bound for kind_animal
        pass

    class ChildGeneric[Z](Parent[Z]):  # leaves T unresolved through Z
        pass

    class ChildUnion(Parent[int | str]):
        pass

    class ChildAliasUnion(Parent[NumberAlias]):
        pass

    class ChildListAlias(Parent[ListAlias]):
        pass

    class UnionBoundParent[T: int | str]:
        kind_union = GenericIntrospectionMethod[T]()

    class UnionBoundChild(UnionBoundParent[int]):
        pass

    class UnionBoundInvalid(UnionBoundParent[float]):  # pyright: ignore[reportInvalidTypeArguments]
        pass

    class AliasBoundParent[T: IntAlias]:
        kind_alias = GenericIntrospectionMethod[T]()

    class AliasBoundChild(AliasBoundParent[IntAlias]):
        pass

    class AliasBoundInvalid(AliasBoundParent[str]):  # pyright: ignore[reportInvalidTypeArguments]
        pass

    class AliasUnionBoundParent[T: NumberAlias]:
        kind_union_alias = GenericIntrospectionMethod[T]()

    class AliasUnionBoundChild(AliasUnionBoundParent[int]):
        pass

    class AliasUnionBoundInvalid(AliasUnionBoundParent[float]):  # pyright: ignore[reportInvalidTypeArguments]
        pass

    def test_class_and_instance_access(self):
        Parent = TestGenericIntrospectionMethod.Parent
        ChildInt = TestGenericIntrospectionMethod.ChildInt

        # Accessing via class
        assert ChildInt.kind() is int
        # Accessing via instance
        inst = ChildInt()
        assert inst.kind() is int
        # Accessing via parent with explicit source
        assert Parent.kind(source=ChildInt) is int

    def test_origin_flag_and_generic_alias_return(self):
        ChildList = TestGenericIntrospectionMethod.ChildList
        # Without origin=True returns the GenericAlias (e.g., list[int])
        alias = ChildList.kind()
        assert typing.get_origin(alias) is list
        assert typing.get_args(alias) == (int,)
        # With origin=True returns the origin
        assert ChildList.kind_origin() is list

    def test_bound_enforced_via_descriptor(self):
        ChildDog = TestGenericIntrospectionMethod.ChildDog
        ChildInvalid = TestGenericIntrospectionMethod.ChildInvalid
        # Valid: Dog is a subclass of Animal
        assert ChildDog.kind_animal() is Dog
        # Invalid: int is not a subclass of Animal
        with pytest.raises(GenericsError) as ei:
            ChildInvalid.kind_animal()
        assert str(ei.value) == f"ChildInvalid.T type argument {int} is not a subclass of {Animal}"

    def test_unresolved_raises_concrete_resolution_error(self):
        ChildGeneric = TestGenericIntrospectionMethod.ChildGeneric
        with pytest.raises(GenericsError) as ei:
            ChildGeneric.kind()
        assert str(ei.value) == "Could not resolve ChildGeneric.T type argument to a concrete type, got <Z>"

    def test_union_specialisation_returns_union(self):
        ChildUnion = TestGenericIntrospectionMethod.ChildUnion

        value = ChildUnion.kind()

        assert value == (int | str)
        assert ChildUnion.kind_origin() is type(int | str)

    def test_union_alias_specialisation_resolves_value(self):
        ChildAliasUnion = TestGenericIntrospectionMethod.ChildAliasUnion

        value = ChildAliasUnion.kind()

        assert value == (int | str)
        assert ChildAliasUnion.kind_origin() is type(int | str)

    def test_list_alias_specialisation_preserves_generic_alias(self):
        ChildListAlias = TestGenericIntrospectionMethod.ChildListAlias

        alias_value = ChildListAlias.kind()

        assert typing.get_origin(alias_value) is list
        assert typing.get_args(alias_value) == (int,)
        assert ChildListAlias.kind_origin() is list

    def test_union_bound_descriptor_enforces_membership(self):
        UnionBoundChild = TestGenericIntrospectionMethod.UnionBoundChild
        UnionBoundInvalid = TestGenericIntrospectionMethod.UnionBoundInvalid

        assert UnionBoundChild.kind_union() is int
        with pytest.raises(GenericsError):
            UnionBoundInvalid.kind_union()

    def test_alias_bound_descriptor_returns_alias(self):
        AliasBoundChild = TestGenericIntrospectionMethod.AliasBoundChild
        AliasBoundInvalid = TestGenericIntrospectionMethod.AliasBoundInvalid

        assert AliasBoundChild.kind_alias() is int
        with pytest.raises(GenericsError):
            AliasBoundInvalid.kind_alias()

    def test_alias_union_bound_descriptor_handles_union(self):
        AliasUnionBoundChild = TestGenericIntrospectionMethod.AliasUnionBoundChild
        AliasUnionBoundInvalid = TestGenericIntrospectionMethod.AliasUnionBoundInvalid

        assert AliasUnionBoundChild.kind_union_alias() is int
        with pytest.raises(GenericsError):
            AliasUnionBoundInvalid.kind_union_alias()
