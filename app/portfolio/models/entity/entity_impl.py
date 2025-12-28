# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import Iterable, Sequence
from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, Self, override

from ....util.callguard import callguard_class
from ....util.helpers.empty_class import empty_class
from ....util.models.superseded import superseded_check
from ....util.models.uid import Uid
from .entity_schema import EntitySchema


if TYPE_CHECKING:
    from ....components.providers.forex import ForexProvider
    from ....context import Context
    from ....util.helpers.decimal import DecimalFactory
    from ....util.logging import Logger
    from ..annotation import Annotation, AnnotationRecord
    from ..entity import Entity


# MARK: Base
@callguard_class(decorator=superseded_check, decorate_public_methods=True)
class EntityImpl[
    T_Annotation_Set: AbstractSet[Annotation],
    T_Uid_Set: AbstractSet[Uid],
](
    EntitySchema[T_Annotation_Set, T_Uid_Set] if TYPE_CHECKING else empty_class(),
    metaclass=ABCMeta,
):
    if TYPE_CHECKING:

        @property
        def log(self) -> Logger: ...

        @property
        def entity(self) -> Entity: ...

        @property
        def previous(self) -> Self | None: ...

        @property
        def is_journal(self) -> bool: ...

    # MARK: Context
    @property
    def context_or_none(self) -> Context | None:
        from ....context import Context

        return Context.get_current_or_none()

    @property
    def context(self) -> Context:
        if (context := self.context_or_none) is None:
            msg = "No active context found. Ensure that you are operating within a valid context."
            raise RuntimeError(msg)
        return context

    @property
    def decimal(self) -> DecimalFactory:
        return self.context.decimal

    @property
    def forex_provider(self) -> ForexProvider:
        return self.context.get_forex_provider()

    # MARK: Annotations
    def iter_annotations[T: Annotation](self, cls: type[T]) -> Iterable[T]:
        for annotation in self.annotations:
            if not isinstance(annotation, cls):
                continue
            yield annotation

    def get_annotations[T: Annotation](self, cls: type[T]) -> Sequence[T]:
        return tuple(self.iter_annotations(cls))

    def get_annotation[T: Annotation](self, cls: type[T]) -> T | None:
        ann = self.get_annotations(cls)

        assert len(ann) <= 1, f"Multiple annotations of type {cls} found for entity {self.uid}"
        return ann[0] if ann else None

    def iter_annotation_records[T: AnnotationRecord](self, cls: type[T]) -> Iterable[T]:
        for annotation in self.annotations:
            record = annotation.record
            if not isinstance(record, cls):
                continue
            yield record

    def get_annotation_records[T: AnnotationRecord](self, cls: type[T]) -> Sequence[T]:
        return tuple(self.iter_annotation_records(cls))

    def get_annotation_record[T: AnnotationRecord](self, cls: type[T]) -> T | None:
        ann = self.get_annotation_records(cls)

        assert len(ann) <= 1, f"Multiple annotation records of type {cls} found for entity {self.uid}"
        return ann[0] if ann else None

    def iter_annotation_uids(self, cls: type[Annotation]) -> Iterable[Uid]:
        for annotation in self.get_annotations(cls):
            yield annotation.uid

    def get_annotation_uids(self, cls: type[Annotation]) -> Sequence[Uid]:
        return tuple(self.iter_annotation_uids(cls))

    # MARK: Utilities
    @override
    def __hash__(self) -> int:
        return hash(self.uid)
