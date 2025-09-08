# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from functools import lru_cache
from typing import override, Iterable, Iterator, Hashable, Any, overload, Self, TYPE_CHECKING, cast as typing_cast, Callable
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema, CoreSchema
from collections.abc import Collection, Sequence
from abc import ABCMeta, abstractmethod

if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison
    from ..journalled.set.ordered_view_set import JournalledOrderedViewSet

from ....util.helpers import generics
from ....util.callguard import callguard_class
from ....util.helpers.instance_lru_cache import instance_lru_cache


@callguard_class()
class OrderedViewCollection[T : Hashable](Collection[T], metaclass=ABCMeta):
    @classmethod
    def get_concrete_content_type(cls, source : type[Self] | None = None) -> type[T]:
        return generics.get_concrete_parent_arg(source or cls, OrderedViewCollection, "T")

    def __init__(self, data : Iterable[T] | None = None, /):
        self._initialize_container(data)

    @abstractmethod
    def _initialize_container(self, data : Iterable[T] | None = None) -> None:
        raise NotImplementedError("Subclasses must implement _initialize_container method.")

    @abstractmethod
    def _get_container(self) -> Collection[T]:
        raise NotImplementedError("Subclasses must implement _get_container method.")

    def _sort_key(self, item : T) -> SupportsRichComparison:
        return typing_cast('SupportsRichComparison', item)

    @property
    def _sort_reverse(self) -> bool:
        return False

    @instance_lru_cache
    def sort(self, key : Callable[[T], SupportsRichComparison] | None = None, reverse : bool | None = None) -> Sequence[T]:
        if key is None:
            key = self._sort_key
        if reverse is None:
            reverse = self._sort_reverse
        return tuple(sorted(self._get_container(), key=key, reverse=reverse))

    @property
    def sorted(self) -> Sequence[T]:
        return self.sort()

    def clear_sort_cache(self) -> None:
        self.sort.cache_clear()



    # MARK: Collection ABC
    @override
    def __contains__(self, value : object) -> bool:
        return value in self._get_container()

    @override
    def __iter__(self) -> Iterator[T]:
        return iter(self.sorted)

    @overload
    def __getitem__(self, index: int) -> T: ...
    @overload
    def __getitem__(self, index: slice) -> Sequence[T]: ...
    def __getitem__(self, index: int | slice) -> T | Sequence[T]:
        return self.sorted[index]

    @override
    def __len__(self):
        return len(self._get_container())

    @override
    def __hash__(self) -> int:
        return hash(self.sorted)

    @override
    def __str__(self) -> str:
        return str(self.sorted)

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.sorted!r}>"



    # MARK: Pydantic
    @classmethod
    @abstractmethod
    def get_core_schema(cls, source, handler) -> CoreSchema:
        raise NotImplementedError("Subclasses must implement get_core_schema method.")

    @classmethod
    def __get_pydantic_core_schema__(cls, source: type[Any], handler: GetCoreSchemaHandler) -> CoreSchema:
        schema = cls.get_core_schema(source, handler)
        return core_schema.no_info_plain_validator_function(
            function= cls.validate_and_coerce,
            json_schema_input_schema= schema,
        )

    @classmethod
    def validate_and_coerce(cls, value: Any) -> Self:
        if not isinstance(value, Iterable):
            raise TypeError(f"Expected an iterable of {cls.get_concrete_content_type().__name__}, got {type(value).__name__}.")

        concrete_item_type = cls.get_concrete_content_type()
        for item in value:
            cls._validate_item(concrete_item_type, item)

        return cls(value)

    @classmethod
    def _validate_item(cls, concrete_item_type : type[T], item: Any) -> None:
        if not isinstance(item, concrete_item_type):
            raise TypeError(f"Expected item of type {concrete_item_type.__name__}, got {type(item).__name__}.")



    # MARK: Journalled Ordered View
    @classmethod
    def get_journalled_type(cls) -> type[JournalledOrderedViewSet]:
        from ..journalled.set.ordered_view_set import JournalledOrderedViewSet
        return JournalledOrderedViewSet