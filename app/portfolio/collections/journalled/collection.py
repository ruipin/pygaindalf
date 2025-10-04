# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta, abstractmethod
from collections.abc import Collection
from typing import Any, Literal, Self, override
from typing import cast as typing_cast

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ....util.callguard import callguard_class
from ....util.helpers import generics
from ....util.mixins import HierarchicalNamedMixin
from .protocols import JournalledCollectionHooksProtocol


@callguard_class()
class JournalledCollection[T_Value: Any, T_Original: Collection, T_Mutable: Collection, T_Immutable: Collection, T_Journal: object](
    HierarchicalNamedMixin, metaclass=ABCMeta
):
    # MARK: Generics
    # fmt: off
    get_concrete_value_type     = generics.GenericIntrospectionMethod[T_Value    ]()
    get_concrete_mutable_type   = generics.GenericIntrospectionMethod[T_Mutable  ]()
    get_concrete_immutable_type = generics.GenericIntrospectionMethod[T_Immutable]()
    get_concrete_journal_type   = generics.GenericIntrospectionMethod[T_Journal  ]()
    # fmt: on

    # MARK: Hooks
    def _call_parent_hook(self, hook_name: Literal["edit"], *args, **kwargs) -> None:
        parent = self.instance_parent
        if parent is not None and isinstance(parent, JournalledCollectionHooksProtocol):
            getattr(parent, f"on_journalled_collection_{hook_name}")(self, *args, **kwargs)

    def _on_edit(self) -> None:
        self._call_parent_hook("edit")

    def __init__(self, original: T_Original, /, **kwargs) -> None:
        super().__init__(**kwargs)
        self._original: T_Original = original
        self._container: T_Mutable | None = None
        self._journal: list[T_Journal] = []
        self._frozen: bool = False

    # MARK: JournalledCollection ABC
    def _get_container(self) -> T_Immutable:
        container = self._container
        return typing_cast("T_Immutable", container if container is not None else self._original)

    def _get_mut_container(self) -> T_Mutable:
        if self._frozen:
            msg = f"Cannot modify frozen {self.instance_hierarchy} of type {type(self).__name__}."
            raise RuntimeError(msg)

        self._copy_on_write()
        return typing_cast("T_Mutable", self._container)

    def _copy_on_write(self) -> None:
        if self._container is None:
            self._container = self.get_concrete_mutable_type()(self._original)  # pyright: ignore[reportCallIssue] as the bounds are not specific enough but we know this is allowed

    @property
    def original(self) -> T_Original:
        return self._original

    @property
    def edited(self) -> bool:
        return self._container is not None or bool(self._journal)

    @property
    def journal(self) -> tuple[T_Journal, ...]:
        return tuple(self._journal)

    def __len__(self) -> int:
        return len(self._get_container())

    @override
    def __str__(self) -> str:
        return str(self._journal)

    @override
    def __repr__(self) -> str:
        return f"<{type(self).__name__}: {self!s})>"

    # MARK: Pydantic
    def make_immutable(self) -> T_Immutable:
        immutable_type = self.get_concrete_immutable_type()

        if self._container is not None:
            return immutable_type(self._container)  # pyright: ignore[reportCallIssue] as the bounds are not specific enough but we know this is allowed
        else:
            original = self._original
            if not isinstance(self._original, immutable_type):
                return immutable_type(original)  # pyright: ignore[reportCallIssue] as the bounds are not specific enough but we know this is allowed
            else:
                return typing_cast("T_Immutable", original)

    @classmethod
    @abstractmethod
    def get_core_schema(cls, source: type[Self], handler: GetCoreSchemaHandler) -> CoreSchema:
        msg = "Subclasses must implement 'get_core_schema' method"
        raise NotImplementedError(msg)

    @classmethod
    def __get_pydantic_core_schema__(cls, source: type[Any], handler: GetCoreSchemaHandler) -> CoreSchema:
        assert cls is source, f"Expected cls to be source, got {type(source).__name__} instead."
        schema = cls.get_core_schema(source, handler)
        return core_schema.no_info_plain_validator_function(
            function=cls.coerce,
            json_schema_input_schema=schema,
        )

    @classmethod
    def coerce(cls, value: Any) -> T_Immutable:
        if isinstance(value, cls):
            return value.make_immutable()

        concrete = cls.get_concrete_immutable_type()

        return concrete(value)  # pyright: ignore[reportCallIssue]

    def freeze(self) -> None:
        self._frozen = True
