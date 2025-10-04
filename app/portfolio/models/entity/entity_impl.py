# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import Iterable
from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, override

from ....util.callguard import callguard_class
from ....util.helpers.empty_class import empty_class
from ...util.superseded import superseded_check
from ...util.uid import Uid
from .entity_schema import EntitySchema


if TYPE_CHECKING:
    from ..annotation import Annotation, AnnotationRecord


# MARK: Base
@callguard_class(decorator=superseded_check, decorate_public_methods=True)
class EntityImpl[
    T_Uid_Set: AbstractSet[Uid],
](
    EntitySchema[T_Uid_Set] if TYPE_CHECKING else empty_class(),
    metaclass=ABCMeta,
):
    # MARK: Annotations
    def get_annotations[T: Annotation](self, cls: type[T]) -> Iterable[T]:
        from ..annotation import Annotation

        for uid in self.annotation_uids:
            annotation = Annotation.narrow_to_instance(uid)
            if not isinstance(annotation, cls):
                continue
            yield annotation

    def get_annotation_records[T: AnnotationRecord](self, cls: type[T]) -> Iterable[T]:
        from ..annotation import AnnotationRecord

        for uid in self.annotation_uids:
            annotation = AnnotationRecord.narrow_to_instance(uid)
            if not isinstance(annotation, cls):
                continue
            yield annotation

    def get_annotation_uids(self, cls: type[Annotation]) -> Iterable[Uid]:
        for annotation in self.get_annotations(cls):
            yield annotation.uid

    # MARK: Utilities
    @override
    def __hash__(self) -> int:
        return hash(self.uid)
