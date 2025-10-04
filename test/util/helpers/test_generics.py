"""Tests for generic helper utilities aligned with the new generics module API.

Covers all public functions (excluding private ones) and ignores GenericIntrospectionMixin.
"""

# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import typing

import pytest

from app.util.helpers.generics import (
    ArgumentInfo,
    GenericsError,
    ParameterInfo,
    get_argument,
    get_argument_info,
    get_argument_infos,
    get_bases_between,
    get_concrete_argument,
    get_concrete_parent_argument,
    get_concrete_parent_argument_origin,
    get_generic_base,
    get_generic_base_or_none,
    get_origin,
    get_origin_or_none,
    get_original_bases,
    get_parameter_info,
    get_parameter_info_or_none,
    get_parameter_infos,
    get_parent_argument,
    get_parent_argument_info,
    get_parent_argument_info_or_none,
    has_parameter,
    iter_argument_infos,
    iter_parameter_infos,
)


"""
Test suite is split into intent-based classes. Each test class defines local
generic types to keep names focused and reusable across classes.
"""


# -------------------------------------------------------------------------------
# MARK: Origin and base helpers
# -------------------------------------------------------------------------------
@pytest.mark.helpers
@pytest.mark.generics
class TestOriginAndBases:
    # Local intent-based classes
    class Pair[T, U: int]:
        pass

    class Plain:
        pass

    class Parent[T]:
        pass

    class Mid[X](Parent[X]):
        pass

    class Leaf(Mid[int]):
        pass

    def test_get_origin_and_generic_base(self):
        Pair = TestOriginAndBases.Pair
        Plain = TestOriginAndBases.Plain
        Mid = TestOriginAndBases.Mid
        Leaf = TestOriginAndBases.Leaf

        assert get_origin_or_none(Pair) is None
        assert get_origin_or_none(Pair[str, int]) is Pair
        assert get_origin(Pair[str, int]) is Pair
        with pytest.raises(GenericsError) as ei:
            get_origin(Pair)
        assert str(ei.value) == "Pair is not a generic class"

        assert get_generic_base_or_none(Pair) is not None
        assert get_generic_base_or_none(Plain) is None
        assert get_generic_base(Pair) is not None
        with pytest.raises(GenericsError) as ei2:
            get_generic_base(Plain)
        assert str(ei2.value) == "Plain is not a generic class"

        bases = get_original_bases(Leaf)
        # Should include Mid[int] as an original base for Leaf
        assert any(get_origin_or_none(b) is Mid for b in bases)


# -------------------------------------------------------------------------------
# MARK: Generic parameter introspection (arg info) and has_arg
# -------------------------------------------------------------------------------
@pytest.mark.helpers
@pytest.mark.generics
class TestArgInfoAndHasArg:
    class Pair[T, U: int]:
        pass

    class Wrapper[T]:
        pass

    def test_iter_and_get_parameter_infos(self):
        Pair = TestArgInfoAndHasArg.Pair
        infos = list(iter_parameter_infos(Pair))
        assert [i.name for i in infos] == ["T", "U"]
        assert [i.position for i in infos] == [0, 1]
        assert all(isinstance(i, ParameterInfo) for i in infos)

        infos_map = get_parameter_infos(Pair)
        assert set(infos_map.keys()) == {"T", "U"}
        assert infos_map["T"].position == 0 and infos_map["U"].position == 1

    def test_get_parameter_info_and_or_none(self):
        Pair = TestArgInfoAndHasArg.Pair
        t_info = get_parameter_info(Pair, "T")
        u_info = get_parameter_info(Pair, "U")
        assert isinstance(t_info, ParameterInfo) and t_info.name == "T" and t_info.position == 0
        assert isinstance(u_info, ParameterInfo) and u_info.name == "U" and u_info.position == 1

        assert get_parameter_info_or_none(Pair, "Z") is None
        with pytest.raises(GenericsError) as ei:
            get_parameter_info(Pair, "Z")
        assert str(ei.value) == "Could not find generic parameter Z in Pair"

    def test_has_arg_variants(self):
        Pair = TestArgInfoAndHasArg.Pair
        Wrapper = TestArgInfoAndHasArg.Wrapper
        # Declared generics exist even if unsubscripted
        assert has_parameter(Pair, "T") is True
        assert has_parameter(Pair, "U") is True
        # Wrong name
        assert has_parameter(Pair, "Z") is False
        # On alias
        assert has_parameter(Pair[str, int], "T") is True
        assert has_parameter(Wrapper[int], "T") is True


# -------------------------------------------------------------------------------
# MARK: Argument specialization and iteration
# -------------------------------------------------------------------------------
@pytest.mark.helpers
@pytest.mark.generics
class TestSpecializations:
    class Pair[T, U: int]:
        pass

    def test_get_argument_info_and_iteration(self):
        Pair = TestSpecializations.Pair
        alias = Pair[str, int]
        spec_t = get_argument_info(alias, "T")
        spec_u = get_argument_info(alias, "U")
        assert isinstance(spec_t, ArgumentInfo) and spec_t.is_concrete and spec_t.value is str
        assert isinstance(spec_u, ArgumentInfo) and spec_u.is_concrete and spec_u.value is int

        specs = list(iter_argument_infos(alias))
        assert {s.parameter.name: s.value for s in specs} == {"T": str, "U": int}

        specs_map = get_argument_infos(alias)
        assert specs_map["T"].value is str and specs_map["U"].value is int


# -------------------------------------------------------------------------------
# MARK: Direct argument access and bounds
# -------------------------------------------------------------------------------
@pytest.mark.helpers
@pytest.mark.generics
class TestDirectArgAccess:
    class Pair[T, U: int]:
        pass

    class Wrapper[T]:
        pass

    def test_get_arg_returns_values(self):
        Pair = TestDirectArgAccess.Pair
        Wrapper = TestDirectArgAccess.Wrapper
        assert get_argument(Pair[str, int], "T") is str
        assert get_argument(Pair[str, int], "U") is int
        assert get_argument(Wrapper[int], "T") is int

    def test_get_concrete_arg_for_generic_typeargs_and_errors(self):
        Pair = TestDirectArgAccess.Pair
        # Concrete generic type argument returns its origin
        assert get_concrete_argument(Pair[list[int], int], "T") is list
        # Non-generic type arguments are rejected
        with pytest.raises(GenericsError) as ei:
            get_concrete_argument(Pair[list[int], int], "U")
        assert str(ei.value) == "Pair.U type argument is not a generic type, got <int>"

    def test_get_arg_bound_violation(self):
        Pair = TestDirectArgAccess.Pair
        with pytest.raises(TypeError) as ei:
            get_argument(Pair[str, str], "U")  # pyright: ignore[reportInvalidTypeArguments]
        assert str(ei.value) == "Pair.U type argument <str> is not a subclass of its bound <int>"

    def test_get_concrete_arg_unresolved_typevar(self):
        Pair = TestDirectArgAccess.Pair
        with pytest.raises(GenericsError) as ei:
            get_concrete_argument(Pair[str, typing.TypeVar("U", bound=int)], "U")
        assert str(ei.value) == "Could not resolve Pair.U type argument to a concrete type"


# -------------------------------------------------------------------------------
# MARK: Parent chain traversal & inheritance mapping
# -------------------------------------------------------------------------------
@pytest.mark.helpers
@pytest.mark.generics
class TestParentTraversal:
    # Intent-based chain types
    class ParentGeneric[T]:
        pass

    class PassThroughMid[X](ParentGeneric[X]):
        pass

    class LeafConcrete(PassThroughMid[int]):
        pass

    class LeafUnresolved[Z](PassThroughMid[Z]):
        pass

    def test_get_bases_between_simple(self):
        ParentGeneric = TestParentTraversal.ParentGeneric
        PassThroughMid = TestParentTraversal.PassThroughMid
        LeafConcrete = TestParentTraversal.LeafConcrete

        chain = get_bases_between(LeafConcrete, ParentGeneric)
        # Expect LeafConcrete -> PassThroughMid[int] -> ParentGeneric[X]
        assert len(chain) == 3
        assert chain[0] is LeafConcrete
        assert get_origin_or_none(chain[1]) is PassThroughMid
        assert get_origin_or_none(chain[2]) is ParentGeneric

    def test_get_parent_arg_specialization_and_helpers(self):
        ParentGeneric = TestParentTraversal.ParentGeneric
        LeafConcrete = TestParentTraversal.LeafConcrete
        LeafUnresolved = TestParentTraversal.LeafUnresolved

        spec = get_parent_argument_info(LeafConcrete, ParentGeneric, "T")
        assert isinstance(spec, ArgumentInfo)
        assert spec.is_concrete and spec.value is int
        assert get_parent_argument(LeafConcrete, ParentGeneric, "T") is int
        assert get_concrete_parent_argument(LeafConcrete, ParentGeneric, "T") is int

        # Or-none variant: unresolved through LeafUnresolved
        spec2 = get_parent_argument_info_or_none(LeafUnresolved, ParentGeneric, "T")
        assert isinstance(spec2, ArgumentInfo)
        assert not spec2.is_concrete and isinstance(spec2.value, typing.TypeVar)
        assert spec2.value.__name__ == "Z"
        with pytest.raises(GenericsError) as ei:
            get_concrete_parent_argument(LeafUnresolved, ParentGeneric, "T")
        assert str(ei.value) == "Could not resolve LeafUnresolved.T type argument to a concrete type, got <Z>"

    def test_get_bases_between_not_subclass(self):
        class Unrelated:
            pass

        ParentGeneric = TestParentTraversal.ParentGeneric
        with pytest.raises(GenericsError) as ei:
            get_bases_between(Unrelated, ParentGeneric)
        assert str(ei.value) == "Unrelated is not a subclass of ParentGeneric"


# -------------------------------------------------------------------------------
# MARK: Generic name remapping & shadowing
# -------------------------------------------------------------------------------
@pytest.mark.helpers
@pytest.mark.generics
class TestNameRemappingAndShadowing:
    # Renaming generics between parent and child (positional mapping but different names)
    class ParentPair[T, U]:
        pass

    class ChildPair[X, Y](ParentPair[X, Y]):  # child uses X,Y instead of T,U
        pass

    # Mismatched names where parent name reused differently plus extra shadowing
    class ShadowParent[T, U]:
        pass

    class ShadowChild[X, T, Y](ShadowParent[Y, T]):  # introduces X and reuses T creating potential ambiguity
        pass

    def test_parent_arg_different_child_generic_names(self):
        ParentPair = TestNameRemappingAndShadowing.ParentPair
        ChildPair = TestNameRemappingAndShadowing.ChildPair
        assert get_parent_argument(ChildPair[int, str], ParentPair, "T") is int
        assert get_parent_argument(ChildPair[int, str], ParentPair, "U") is str

    def test_parent_arg_mismatched_and_shadowed_names(self):
        ShadowParent = TestNameRemappingAndShadowing.ShadowParent
        ShadowChild = TestNameRemappingAndShadowing.ShadowChild
        assert get_parent_argument(ShadowChild[int, int, str], ShadowParent, "T") is str
        assert get_parent_argument(ShadowChild[int, int, str], ShadowParent, "U") is int

    # Bound-related renaming/shadowing tests moved to TestBoundsAndPropagation


# -------------------------------------------------------------------------------
# MARK: Bounds propagation and enforcement
# -------------------------------------------------------------------------------
@pytest.mark.helpers
@pytest.mark.generics
class TestBoundsAndPropagation:
    # Shared base and subclasses for bound tests
    class Animal: ...

    class Dog(Animal): ...

    class Cat(Animal): ...

    # Shared generic classes for bounds scenarios
    class BoundOnly[A: Animal]:
        pass

    class UnboundAndBound[X, Y: int]:
        pass

    class Kennel[P: Animal]:
        pass

    class ParentBound[T: Animal]:
        pass

    class MidPass[X: Animal](ParentBound[X]):
        pass

    class LeafDog(MidPass[Dog]):
        pass

    class LeafInt(MidPass[int]):  # pyright: ignore[reportInvalidTypeArguments]
        pass

    class ParentPairBound[T: Animal, U]:
        pass

    class ChildRenamed[X: Animal, Y](ParentPairBound[X, Y]):
        pass

    class Parent[T: Animal, U]:
        pass

    class Child[X, T, Y: Animal](Parent[Y, T]):
        pass

    def test_default_to_bound_for_unsubscripted(self):
        Animal = TestBoundsAndPropagation.Animal
        BoundOnly = TestBoundsAndPropagation.BoundOnly
        UnboundAndBound = TestBoundsAndPropagation.UnboundAndBound

        spec_a = get_argument_info(BoundOnly, "A")
        assert spec_a.value_or_bound is Animal

        spec_x = get_argument_info(UnboundAndBound, "X")
        spec_y = get_argument_info(UnboundAndBound, "Y")
        assert not spec_x.is_concrete and isinstance(spec_x.value, typing.TypeVar) and spec_x.value.__name__ == "X"
        assert not spec_y.is_concrete and isinstance(spec_y.value, typing.TypeVar)
        assert spec_y.value_or_bound is int

    def test_subclass_of_bound_is_accepted(self):
        Dog = TestBoundsAndPropagation.Dog
        Kennel = TestBoundsAndPropagation.Kennel
        assert get_argument(Kennel[Dog], "P") is Dog

    def test_bound_enforced_through_traversal(self):
        Dog = TestBoundsAndPropagation.Dog
        ParentBound = TestBoundsAndPropagation.ParentBound
        LeafDog = TestBoundsAndPropagation.LeafDog
        LeafInt = TestBoundsAndPropagation.LeafInt

        # Concrete subtype of bound resolves correctly
        assert get_parent_argument(LeafDog, ParentBound, "T") is Dog

        # Violating bound during traversal should raise
        with pytest.raises(TypeError) as ei:
            get_parent_argument(LeafInt, ParentBound, "T")
        assert str(ei.value) == "ParentBound.T type argument <int> is not a subclass of its bound <Animal>"

    def test_renamed_with_bound_enforced(self):
        Dog = TestBoundsAndPropagation.Dog
        ParentPairBound = TestBoundsAndPropagation.ParentPairBound
        ChildRenamed = TestBoundsAndPropagation.ChildRenamed

        # Subclass of bound accepted
        assert get_parent_argument(ChildRenamed[Dog, int], ParentPairBound, "T") is Dog
        assert get_parent_argument(ChildRenamed[Dog, int], ParentPairBound, "U") is int

        # Violates bound
        with pytest.raises(TypeError) as ei:
            get_parent_argument(ChildRenamed[int, str], ParentPairBound, "T")  # pyright: ignore[reportInvalidTypeArguments]
        assert str(ei.value) == "ParentPairBound.T type argument <int> is not a subclass of its bound <Animal>"

    def test_shadowed_and_reordered_with_bound_enforced(self):
        Cat = TestBoundsAndPropagation.Cat
        Parent = TestBoundsAndPropagation.Parent
        Child = TestBoundsAndPropagation.Child

        # Valid: T mapped from child's Y which is Cat (subclass of Animal)
        assert get_parent_argument(Child[int, int, Cat], Parent, "T") is Cat
        assert get_parent_argument(Child[int, int, Cat], Parent, "U") is int

        # Invalid: T mapped from child's Y which is int (not Animal)
        with pytest.raises(TypeError) as ei:
            get_parent_argument(Child[int, int, int], Parent, "T")  # pyright: ignore[reportInvalidTypeArguments]
        assert str(ei.value) == "Parent.T type argument <int> is not a subclass of its bound <Animal>"


# -------------------------------------------------------------------------------
# MARK: Union arguments
# -------------------------------------------------------------------------------
@pytest.mark.helpers
@pytest.mark.generics
class TestUnionArguments:
    class Container[T]:
        pass

    class UnionLeaf(Container[int | str]):
        pass

    def test_union_argument_round_trip(self):
        Container = TestUnionArguments.Container

        alias = Container[int | str]
        info = get_argument_info(alias, "T")

        assert info.is_concrete
        assert info.value == (int | str)
        assert list(get_argument_infos(alias).keys()) == ["T"]
        assert get_argument(alias, "T") == (int | str)
        assert get_concrete_argument(alias, "T") is type(int | str)

    def test_union_argument_through_parent_traversal(self):
        Container = TestUnionArguments.Container
        UnionLeaf = TestUnionArguments.UnionLeaf

        result = get_parent_argument(UnionLeaf, Container, "T")

        assert result == (int | str)
        assert get_concrete_parent_argument(UnionLeaf, Container, "T") == (int | str)
        assert get_concrete_parent_argument_origin(UnionLeaf, Container, "T") is type(int | str)


# -------------------------------------------------------------------------------
# MARK: Type alias arguments
# -------------------------------------------------------------------------------
@pytest.mark.helpers
@pytest.mark.generics
class TestAliasArguments:
    type SequenceAlias = list[int]

    class Container[T]:
        pass

    class AliasLeaf(Container[SequenceAlias]):
        pass

    def test_type_alias_argument_round_trip(self):
        Container = TestAliasArguments.Container
        SequenceAlias = TestAliasArguments.SequenceAlias

        alias = Container[SequenceAlias]
        info = get_argument_info(alias, "T")

        assert info.is_concrete
        assert typing.get_origin(info.value) is list
        assert typing.get_args(info.value) == (int,)
        assert get_argument(alias, "T") == info.value
        assert get_concrete_argument(alias, "T") is list

    def test_type_alias_argument_through_parent_traversal(self):
        Container = TestAliasArguments.Container
        AliasLeaf = TestAliasArguments.AliasLeaf
        result = get_parent_argument(AliasLeaf, Container, "T")

        assert typing.get_origin(result) is list
        assert typing.get_args(result) == (int,)
        assert get_concrete_parent_argument(AliasLeaf, Container, "T") == result
        assert get_concrete_parent_argument_origin(AliasLeaf, Container, "T") is list


# -------------------------------------------------------------------------------
# MARK: Union alias interactions
# -------------------------------------------------------------------------------
@pytest.mark.helpers
@pytest.mark.generics
class TestUnionAliasInteractions:
    type NumberAlias = int | str

    class Container[T]:
        pass

    class AliasLeaf(Container[NumberAlias]):
        pass

    def test_union_alias_argument_round_trip(self):
        Container = TestUnionAliasInteractions.Container
        NumberAlias = TestUnionAliasInteractions.NumberAlias

        alias = Container[NumberAlias]
        info = get_argument_info(alias, "T")

        assert info.is_concrete
        assert info.value == (int | str)
        assert get_argument(alias, "T") == (int | str)
        assert get_concrete_argument(alias, "T") is type(int | str)

    def test_union_alias_argument_through_parent_traversal(self):
        Container = TestUnionAliasInteractions.Container
        AliasLeaf = TestUnionAliasInteractions.AliasLeaf

        result = get_parent_argument(AliasLeaf, Container, "T")

        assert result == (int | str)
        assert get_concrete_parent_argument(AliasLeaf, Container, "T") == (int | str)
        assert get_concrete_parent_argument_origin(AliasLeaf, Container, "T") is type(int | str)


# -------------------------------------------------------------------------------
# MARK: TypeVar bounds with unions and aliases
# -------------------------------------------------------------------------------
@pytest.mark.helpers
@pytest.mark.generics
class TestTypeVarCompositeBounds:
    type SequenceAlias = list[int]
    type NumberUnionAlias = int | str

    class UnionParent[T: int | str]:
        pass

    class UnionChild(UnionParent[int]):
        pass

    class UnionChildInvalid(UnionParent[float]):  # pyright: ignore[reportInvalidTypeArguments]
        pass

    class AliasParent[T: SequenceAlias]:
        pass

    class AliasChild(AliasParent[SequenceAlias]):
        pass

    class AliasChildInvalid(AliasParent[int]):  # pyright: ignore[reportInvalidTypeArguments]
        pass

    class AliasUnionParent[T: NumberUnionAlias]:
        pass

    class AliasUnionChild(AliasUnionParent[int]):
        pass

    class AliasUnionChildInvalid(AliasUnionParent[float]):  # pyright: ignore[reportInvalidTypeArguments]
        pass

    def test_union_bound_allows_members(self):
        Parent = TestTypeVarCompositeBounds.UnionParent
        Child = TestTypeVarCompositeBounds.UnionChild

        assert get_parent_argument(Child, Parent, "T") is int

    def test_union_bound_rejects_non_members(self):
        Parent = TestTypeVarCompositeBounds.UnionParent
        BadChild = TestTypeVarCompositeBounds.UnionChildInvalid

        with pytest.raises(TypeError):
            get_parent_argument(BadChild, Parent, "T")

    def test_alias_bound_returns_alias_value(self):
        Parent = TestTypeVarCompositeBounds.AliasParent
        Child = TestTypeVarCompositeBounds.AliasChild

        result = get_parent_argument(Child, Parent, "T")

        assert typing.get_origin(result) is list
        assert typing.get_args(result) == (int,)

    def test_alias_bound_rejects_non_alias(self):
        Parent = TestTypeVarCompositeBounds.AliasParent
        BadChild = TestTypeVarCompositeBounds.AliasChildInvalid

        with pytest.raises(TypeError):
            get_parent_argument(BadChild, Parent, "T")

    def test_alias_union_bound_allows_members(self):
        Parent = TestTypeVarCompositeBounds.AliasUnionParent
        Child = TestTypeVarCompositeBounds.AliasUnionChild

        assert get_parent_argument(Child, Parent, "T") is int

    def test_alias_union_bound_rejects_non_members(self):
        Parent = TestTypeVarCompositeBounds.AliasUnionParent
        BadChild = TestTypeVarCompositeBounds.AliasUnionChildInvalid

        with pytest.raises(TypeError):
            get_parent_argument(BadChild, Parent, "T")
