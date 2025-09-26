# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref
from typing import override, Any, Self, cast as typing_cast

from ..entity import Entity, SupersededError
from ..uid import Uid

from .annotation_journal import AnnotationJournal


class Annotation[T_Journal : AnnotationJournal](Entity[T_Journal]):
    # MARK: Construction / Initialization
    @classmethod
    def create[T : Annotation](cls : type[T], entity_or_uid : Entity | Uid, /, **kwargs) -> T:
        if 'instance_parent' in kwargs or 'instance_parent_weakref' in kwargs:
            raise ValueError("instance_parent cannot be specified directly; use the entity parameter instead.")

        entity = Entity.narrow_to_entity(entity_or_uid)
        if entity.superseded:
            raise SupersededError(f"Cannot create annotation for superseded entity {entity}.")

        return cls(instance_parent=weakref.ref(entity), **kwargs)


    @override
    def model_post_init(self, context : Any) -> None:
        super().model_post_init(context)

        # Add self to parent's annotations
        self.entity_parent.on_annotation_created(self)

    @override
    def _propagate_deletion(self) -> None:
        parent = self.entity_parent_or_none
        if parent is not None:
            self.entity_parent.on_annotation_deleted(self)
        else:
            self.log.warning("Annotation %s has no parent during deletion propagation.", self)

        super()._propagate_deletion()