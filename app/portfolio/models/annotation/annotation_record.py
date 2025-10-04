# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import TYPE_CHECKING, Any, override

from ....util.helpers.empty_class import empty_class
from ..entity import EntityRecord
from .annotation_impl import AnnotationImpl
from .annotation_journal import AnnotationJournal
from .annotation_schema import AnnotationSchema


class AnnotationRecord[
    T_Journal: AnnotationJournal,
](
    AnnotationImpl,
    AnnotationSchema if not TYPE_CHECKING else empty_class(),
    EntityRecord[T_Journal],
    init=False,
    unsafe_hash=True,
):
    @override
    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)

        # Add self to parent's annotations
        self.record_parent.on_annotation_record_created(self)

    @override
    def propagate_deletion(self) -> None:
        parent = self.record_parent_or_none
        if parent is not None:
            self.record_parent.on_annotation_record_deleted(self)
        else:
            self.log.warning(t"Annotation record {self} has no parent during deletion propagation.")

        super().propagate_deletion()
