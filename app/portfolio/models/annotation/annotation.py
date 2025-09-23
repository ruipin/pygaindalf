# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref
from typing import override, Any, Self, cast as typing_cast

from ..entity import Entity
from ..uid import Uid

from .annotation_journal import AnnotationJournal


class Annotation[T_Journal : AnnotationJournal](Entity[T_Journal]):
    @classmethod
    @override
    def get_journal_class(cls) -> type[T_Journal]:
        from .annotation_journal import AnnotationJournal
        return typing_cast(type[T_Journal], AnnotationJournal)


    # MARK: Construction / Initialization
    @classmethod
    def create[T : Annotation](cls : type[T], entity : Entity, /, **kwargs) -> T:
        if 'instance_parent' in kwargs or 'instance_parent_weakref' in kwargs:
            raise ValueError("instance_parent cannot be specified directly; use the entity parameter instead.")
        if entity is None or not isinstance(entity, Entity):
            raise ValueError("entity must be a valid Entity instance")

        return cls(instance_parent=weakref.ref(entity), **kwargs)


    @override
    def model_post_init(self, context : Any) -> None:
        super().model_post_init(context)

        # Add self to parent's annotations
        self.entity_parent.on_annotation_created(self)