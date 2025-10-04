# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref

from abc import ABCMeta
from typing import TYPE_CHECKING

from ....util.helpers.empty_class import empty_class
from ...util import SupersededError, Uid
from ..entity import Entity, EntityRecord
from .annotation_journal import AnnotationJournal
from .annotation_record import AnnotationRecord


class Annotation[
    T_Record: AnnotationRecord,
    T_Journal: AnnotationJournal,
](
    AnnotationRecord if TYPE_CHECKING else empty_class(),
    Entity[T_Record, T_Journal],
    metaclass=ABCMeta,
    init=False,
):
    # MARK: Construction / Initialization
    @classmethod
    def create[T: Annotation](cls: type[T], entity_or_uid: Entity | EntityRecord | Uid, /, **kwargs) -> T:
        if "instance_parent" in kwargs or "instance_parent_weakref" in kwargs:
            msg = "instance_parent cannot be specified directly; use the entity parameter instead."
            raise ValueError(msg)

        entity = Entity.narrow_to_instance(entity_or_uid)
        if entity.deleted:
            msg = f"Cannot create annotation for deleted entity {entity}."
            raise SupersededError(msg)

        return cls(instance_parent=weakref.ref(entity), **kwargs)  # pyright: ignore[reportCallIssue]


# Register the proxy with the corresponding entity class to ensure isinstance and issubclass checks work correctly.
AnnotationRecord.register_entity_class(Annotation)
