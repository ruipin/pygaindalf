# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import typing

from typing import get_type_hints

import pytest

from frozendict import frozendict

from app.util.helpers.type_hints import (
    CachedTypeHintsMixin,
    SupportsCachedTypeHints,
    iterate_type_hints,
    match_type_hint,
    validate_type_hint,
)


class _SampleWithHints(CachedTypeHintsMixin):
    required: int
    optional: str | None = None


class _SampleNoMixin:
    required: int
    optional: str | None = None


@pytest.mark.helpers
@pytest.mark.type_hints
class TestTypeHints:
    def test_cached_type_hints_mixin_returns_frozendict_and_caches_identity(self) -> None:
        first = _SampleWithHints.__cached_type_hints__
        second = _SampleWithHints.__cached_type_hints__

        assert isinstance(first, frozendict)
        assert first is second
        assert dict(first) == get_type_hints(_SampleWithHints)

    def test_supports_cached_type_hints_runtime_protocol(self) -> None:
        instance = _SampleWithHints()

        assert isinstance(instance, SupportsCachedTypeHints)
        assert isinstance(_SampleWithHints, SupportsCachedTypeHints)
        assert not isinstance(_SampleNoMixin(), SupportsCachedTypeHints)

    def test_cached_type_hints_matches_typing_get_type_hints(self) -> None:
        hints = _SampleWithHints.__cached_type_hints__

        assert dict(hints) == get_type_hints(_SampleWithHints)

    def test_cached_type_hints_contains_expected_entries(self) -> None:
        hints = _SampleWithHints.__cached_type_hints__

        assert set(hints.keys()) == {"required", "optional"}
        assert hints["required"] is int
        assert hints["optional"] == (str | None)

    def test_cached_type_hints_mapping_is_immutable(self) -> None:
        hints = _SampleWithHints.__cached_type_hints__

        assert set(hints.keys()) == {"required", "optional"}
        assert hints["required"] is int
        assert hints["optional"] == (str | None)

    def test_match_type_hint_returns_matching_branch_for_union(self) -> None:
        result = match_type_hint(int, int | str)

        assert result is int

    def test_match_type_hint_returns_none_when_type_not_in_union(self) -> None:
        result = match_type_hint(float, int | str)

        assert result is None

    def test_match_type_hint_handles_generic_alias(self) -> None:
        alias = list[int]

        result = match_type_hint(list, alias)

        assert result == alias

    def test_match_type_hint_with_forward_ref_raises_not_implemented(self) -> None:
        with pytest.warns(UserWarning, match=r"ForwardRef\('Missing'\) type hint matching not implemented"):
            match_type_hint(int, typing.ForwardRef("Missing"))

    def test_validate_type_hint_true_when_type_matches(self) -> None:
        assert validate_type_hint(int, int | str)

    def test_validate_type_hint_false_when_type_mismatch(self) -> None:
        assert not validate_type_hint(float, int | str)

    def test_iterate_type_hints_returns_hint_for_non_union(self) -> None:
        alias = list[int]

        assert list(iterate_type_hints(alias)) == [alias]

    def test_iterate_type_hints_flattens_union(self) -> None:
        hint = int | str

        assert list(iterate_type_hints(hint)) == [int, str]

    def test_iterate_type_hints_flattens_nested_union(self) -> None:
        hint = int | str | float

        assert list(iterate_type_hints(hint)) == [int, str, float]

    def test_iterate_type_hints_preserves_forward_refs(self) -> None:
        ref = typing.ForwardRef("Foo")
        hint = int | ref

        assert list(iterate_type_hints(hint)) == [int, ref]
