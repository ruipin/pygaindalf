# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import override

from ..entity import EntityRecord
from .annotation_impl import AnnotationImpl
from .annotation_journal import AnnotationJournal
from .annotation_schema import AnnotationSchema


class AnnotationRecord[
    T_Journal: AnnotationJournal,
](
    AnnotationImpl,
    EntityRecord[T_Journal],
    AnnotationSchema,
    init=False,
    unsafe_hash=True,
):
    @override
    def propagate_deletion(self) -> None:
        parent = self.record_parent_or_none
        if parent is not None:
            self.entity_parent.on_annotation_deleted(self.uid)
        else:
            self.log.warning(t"Annotation record {self} has no parent during deletion propagation.")

        super().propagate_deletion()
