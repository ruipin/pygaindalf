# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools

from abc import ABCMeta, abstractmethod
from collections.abc import Callable, Collection, Hashable, Iterable, Iterator, Sequence
from typing import TYPE_CHECKING, Any, Self, overload, override
from typing import cast as typing_cast

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison

    from ..journalled.set.ordered_view_set import JournalledOrderedViewSet

from ....util.callguard import callguard_class
from ....util.helpers import generics
from ....util.helpers.instance_lru_cache import instance_lru_cache
from ...models.entity import Entity
from ...util.uid import Uid
from .protocols import SortKeyProtocol


@callguard_class()
class OrderedViewCollection[T: Hashable](Collection[T], metaclass=ABCMeta):
    get_content_type = generics.GenericIntrospectionMethod[T]()

    def __init__(self, data: Iterable[T] | None = None, /) -> None:
        self._initialize_container(data)

    @abstractmethod
    def _initialize_container(self, data: Iterable[T] | None = None) -> None:
        msg = "Subclasses must implement _initialize_container method."
        raise NotImplementedError(msg)

    @abstractmethod
    def _get_container(self) -> Collection[T]:
        msg = "Subclasses must implement _get_container method."
        raise NotImplementedError(msg)

    def item_sort_key(self, item: T) -> SupportsRichComparison:
        if isinstance(item, Uid):
            item = Entity.by_uid(item)
        if isinstance(item, SortKeyProtocol):
            return item.sort_key()
        return typing_cast("SupportsRichComparison", item)

    @property
    def item_sort_reverse(self) -> bool:
        return False

    @instance_lru_cache
    def sort(self, *, key: Callable[[T], SupportsRichComparison] | None = None, reverse: bool | None = None) -> Sequence[T]:
        if key is None:
            key = self.item_sort_key
        if reverse is None:
            reverse = self.item_sort_reverse
        return tuple(sorted(self._get_container(), key=key, reverse=reverse))

    @property
    def sorted(self) -> Sequence[T]:
        return self.sort()

    def clear_sort_cache(self) -> None:
        self.sort.cache_clear()

    # MARK: Collection ABC
    @override
    def __contains__(self, value: object) -> bool:
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
    def __len__(self) -> int:
        return len(self._get_container())

    @override
    def __hash__(self) -> int:
        return hash(self.sorted)

    @override
    def __str__(self) -> str:
        return str(self.sorted)

    @override
    def __repr__(self) -> str:
        return f"<{type(self).__name__}: {self.sorted!r}>"

    # MARK: Pydantic
    @classmethod
    @abstractmethod
    def get_core_schema(cls, source, handler) -> CoreSchema:  # noqa: ANN001
        msg = "Subclasses must implement get_core_schema method."
        raise NotImplementedError(msg)

    @classmethod
    def __get_pydantic_core_schema__(cls, source: type[Any], handler: GetCoreSchemaHandler) -> CoreSchema:
        schema = cls.get_core_schema(source, handler)
        return core_schema.no_info_plain_validator_function(
            function=functools.partial(cls.validate_and_coerce, source=source),
            json_schema_input_schema=schema,
        )

    @classmethod
    def validate_and_coerce(cls, value: Any, *, source: type[Self] | None = None) -> Self:
        if not isinstance(value, Iterable):
            msg = f"Expected an iterable of {cls.get_content_type().__name__}, got {type(value).__name__}."
            raise TypeError(msg)

        concrete_item_type = cls.get_content_type()
        for item in value:
            cls._validate_item(concrete_item_type, item, source=source)

        return cls(value)

    @classmethod
    def _validate_item(cls, concrete_item_type: type[T], item: Any, *, source: type[Self] | None = None) -> None:  # noqa: ARG003
        if not isinstance(item, concrete_item_type):
            msg = f"Expected item of type {concrete_item_type.__name__}, got {type(item).__name__}."
            raise TypeError(msg)

    # MARK: Journalled Ordered View
    @classmethod
    def get_journalled_type(cls) -> type[JournalledOrderedViewSet]:
        from ..journalled.set.ordered_view_set import JournalledOrderedViewSet

        return JournalledOrderedViewSet


class OrderedViewUidCollection[T: Entity](OrderedViewCollection[Uid], metaclass=ABCMeta):
    get_entity_type = generics.GenericIntrospectionMethod[T]()

    @classmethod
    @override
    def _validate_item(cls, concrete_item_type: type[Uid], item: Any, *, source: type[Self] | None = None) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        super()._validate_item(concrete_item_type, item, source=source)

        entity_type = cls.get_entity_type(source=source)
        if item.namespace != (ns := entity_type.uid_namespace()):
            msg = f"Invalid entity UID namespace: expected '{ns}', got '{item.namespace}'."
            raise ValueError(msg)
