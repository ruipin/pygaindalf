# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections import abc as abcs

import pytest

from app.util.helpers.abc_info import (
    ABCInfo,
    get_abc_info,
    get_class_attribute_abc_info,
)
from app.util.helpers.type_hints import CachedTypeHintsMixin


class _CollectionHolder(CachedTypeHintsMixin):
    mapped: dict[str, int]
    label: str

    def __init__(self) -> None:
        self.mapped = {}
        self.label = "identifier"
        self.sequenced = []


@pytest.mark.helpers
@pytest.mark.abc_info
class TestABCInfo:
    def test_get_abc_info_for_list_instance_reports_sequence_traits(self) -> None:
        info = get_abc_info([1, 2, 3])

        assert isinstance(info, ABCInfo)
        assert info.source is list
        assert info.source_origin is list
        assert info.sequence is True
        assert info.mutable is True
        assert info.mapping is False
        assert info.set is False
        assert not info.specialized
        assert not info.has_key
        assert info.value_type is None
        assert info.value_origin is None
        assert abcs.MutableSequence in info.abcs
        assert info.str_or_bytes is False
        assert info.matches(abcs.Sequence)

    def test_get_abc_info_uses_type_hints_to_resolve_value_type(self) -> None:
        holder = _CollectionHolder()

        info = get_abc_info(holder.mapped, namespace=_CollectionHolder, attr="mapped")

        assert info.source == dict[str, int]
        assert info.source_origin is dict
        assert info.mapping is True
        assert info.mutable is True
        assert info.sequence is False
        assert info.has_key
        assert info.specialized is True
        assert info.key_type is str
        assert info.key_origin is str
        assert info.value_type is int
        assert info.value_origin is int
        assert info.str_or_bytes is False
        assert abcs.MutableMapping in info.abcs

    def test_get_abc_info_handles_string_like_containers(self) -> None:
        holder = _CollectionHolder()

        info = get_abc_info(holder.label, namespace=_CollectionHolder, attr="label")

        assert info is not None
        assert info.source is str
        assert info.source_origin is str
        assert info.value_type is str
        assert info.sequence is True
        assert info.specialized is True
        assert info.str_or_bytes is True

    def test_get_class_attribute_abc_info_returns_none_without_type_hints(self) -> None:
        class _NoHint(CachedTypeHintsMixin):
            def __init__(self) -> None:
                self.items = []

        assert get_class_attribute_abc_info(_NoHint, "items") is None
