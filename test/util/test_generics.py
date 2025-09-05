"""Tests for generic helper utilities.

Style mirrors other test modules: SPDX header, class-based tests with a pytest
marker (helpers) and descriptive method names.
"""

# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest
from typing import TypeVar

from app.util.helpers.generics import (
    GenericsError,
    get_arg_info,
    get_arg,
    get_concrete_arg,
    get_bases_between,
    get_parent_arg,
    get_concrete_parent_arg,
    has_arg,
)

#-------------------------------------------------------------------------------
# MARK: Class definitions
#-------------------------------------------------------------------------------

# Define generic classes using Python 3.12 syntax
class Base[T, U: int]:
    """A simple generic base with two type variables, one of them bound to int."""
    pass


class Concrete(Base[str, int]):
    pass


class Partial[U: int](Base[str, U]):  # leaves U unresolved (still a TypeVar)
    pass


class WrongBound(Base[str, str]):  # violates bound for U (expects int)  # type: ignore[reportInvalidTypeArguments]
    pass


class Other[T]:
    pass


class Unrelated:
    pass


# Multi-level inheritance chain to test parent traversal
class P[T]:
    pass


class Q[X](P[X]):
    pass


class R(Q[int]):
    pass


class QPartial[X](P[X]):
    pass


class RPartial[Z](QPartial[Z]):
    pass


# Renaming generics between parent and child (positional mapping but different names)
class A[T, U]:
    pass


class B[X, Y](A[X, Y]):  # child uses X,Y instead of T,U
    pass


# Mismatched names where parent name reused differently plus extra shadowing
class C1[T, U]:
    pass


class C2[X, T, Y](C1[Y, T]):  # introduces X and reuses T creating potential ambiguity
    pass


#-------------------------------------------------------------------------------
# MARK: Unit tests
#-------------------------------------------------------------------------------
@pytest.mark.helpers
@pytest.mark.generics
class TestGenericHelpers:
    #-------------------------------------------------------------------------------
    # MARK: Generic parameter introspection (arg info)
    #-------------------------------------------------------------------------------
    def test_get_arg_info_success(self):
        index_t, tv_t = get_arg_info(Base, "T")
        index_u, tv_u = get_arg_info(Base, "U")
        assert (index_t, tv_t.__name__) == (0, "T")
        assert (index_u, tv_u.__name__) == (1, "U")

    def test_get_arg_info_missing(self):
        with pytest.raises(GenericsError) as ei:
            get_arg_info(Base, "Z")
        assert "Could not find generic argument Z in Base" == str(ei.value)

    #-------------------------------------------------------------------------------
    # MARK: has_arg existence checks
    #-------------------------------------------------------------------------------
    def test_has_arg_concrete(self):
        assert has_arg(Base[str, int], "T") is True
        assert has_arg(Base[str, int], "U") is True

    def test_has_arg_unsubscripted(self):
        # Unsubscripted generic class should not report having resolvable args
        assert has_arg(Base, "T") is False
        assert has_arg(Base, "U") is False

    def test_has_arg_missing_name(self):
        assert has_arg(Base[str, int], "Z") is False
        assert has_arg(Base, "Z") is False

    def test_has_arg_partial_and_unresolved(self):
        # Partial[int] resolves U, unsubscripted Partial leaves it unresolved
        assert has_arg(Partial[int], "U") is True
        assert has_arg(Partial, "U") is False

    def test_has_arg_other_generic(self):
        assert has_arg(Other[int], "T") is True
        assert has_arg(Other, "T") is False

    #-------------------------------------------------------------------------------
    # MARK: Direct concrete argument resolution
    #-------------------------------------------------------------------------------
    def test_get_concrete_arg_success(self):
        assert get_concrete_arg(Base[str, int], "T") is str
        assert get_concrete_arg(Base[str, int], "U") is int

    #-------------------------------------------------------------------------------
    # MARK: Unresolved TypeVar handling
    #-------------------------------------------------------------------------------
    def test_get_arg_returns_typevar_for_unresolved(self):
        # Using a parametrized instantiation keeps U as a TypeVar
        arg = get_arg(Base[str, TypeVar("U", bound=int)], "U")
        assert isinstance(arg, TypeVar)
        assert arg.__name__ == "U"

    def test_get_concrete_arg_unresolved_typevar(self):
        with pytest.raises(GenericsError) as ei:
            get_concrete_arg(Base[str, TypeVar("U", bound=int)], "U")
        assert "Could not resolve Base.U type argument to a concrete type" == str(ei.value)

    #-------------------------------------------------------------------------------
    # MARK: Resolved TypeVar handling
    #-------------------------------------------------------------------------------
    def test_get_arg_returns_concrete_for_resolved(self):
        assert get_arg(Base[str, int], "T") is str
        assert get_arg(Base[str, int], "U") is int

    def test_get_parent_arg_resolved(self):
        assert get_parent_arg(R, P, "T") is int
        assert get_concrete_parent_arg(R, P, "T") is int

    #-------------------------------------------------------------------------------
    # MARK: Bound violations
    #-------------------------------------------------------------------------------
    def test_get_arg_bound_violation(self):
        with pytest.raises(TypeError) as ei:
            get_arg(Base[str, str], "U")  # pyright: ignore[reportInvalidTypeArguments]
        assert "Base.U type argument <str> is not a subclass of its bound <int>" == str(ei.value)

    def test_get_concrete_arg_bound_violation(self):
        with pytest.raises(TypeError) as ei:
            get_concrete_arg(Base[str, str], "U")  # pyright: ignore[reportInvalidTypeArguments]
        assert "Base.U type argument <str> is not a subclass of its bound <int>" == str(ei.value)

    #-------------------------------------------------------------------------------
    # MARK: Non-generic / incorrectly used bases
    #-------------------------------------------------------------------------------
    def test_get_arg_missing_base(self):
        with pytest.raises(GenericsError) as ei:
            get_arg(Unrelated, "T")
        assert str(ei.value) == "Unrelated is not a generic class"

    def test_get_concrete_arg_missing_base(self):
        with pytest.raises(GenericsError) as ei:
            get_concrete_arg(Unrelated, "T")
        assert str(ei.value) == "Unrelated is not a generic class"

    def test_get_arg_wrong_generic_class(self):
        with pytest.raises(GenericsError):
            get_arg(Other, "T")
        assert get_arg(Other[int], "T") is int

    def test_get_concrete_arg_wrong_generic_class(self):
        with pytest.raises(GenericsError):
            get_concrete_arg(Other, "T")
        assert get_concrete_arg(Other[int], "T") is int

    #-------------------------------------------------------------------------------
    # MARK: Parent chain traversal & inheritance mapping
    #-------------------------------------------------------------------------------
    def test_get_bases_between_simple(self):
        chain = get_bases_between(R, P)
        # Expect R -> Q[int] -> P
        assert len(chain) == 3
        assert chain[0].__name__ == "R"
        assert chain[-1].__name__ == "P"

    def test_get_parent_arg_partial_and_concrete(self):
        assert get_parent_arg(RPartial[str], P, "T") is str
        assert get_concrete_parent_arg(RPartial[str], P, "T") is str

    def test_get_parent_arg_unresolved(self):
        tv = get_parent_arg(RPartial, P, "T")
        assert isinstance(tv, TypeVar)
        assert tv.__name__ == "Z"
        with pytest.raises(GenericsError):
            get_concrete_parent_arg(RPartial, P, "T")

    def test_get_parent_arg_error_not_subclass(self):
        with pytest.raises(GenericsError) as ei:
            get_bases_between(Unrelated, P)
        assert "Unrelated is not a subclass of P" == str(ei.value)

    #-------------------------------------------------------------------------------
    # MARK: Generic name remapping & shadowing
    #-------------------------------------------------------------------------------
    def test_parent_arg_different_child_generic_names(self):
        assert get_parent_arg(B[int, str], A, "T") is int
        assert get_parent_arg(B[int, str], A, "U") is str


    def test_parent_arg_mismatched_and_shadowed_names(self):
        assert get_parent_arg(C2[int, int, str], C1, "T") is str
        assert get_parent_arg(C2[int, int, str], C1, "U") is int