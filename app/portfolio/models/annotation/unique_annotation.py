# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref

from collections.abc import Mapping
from typing import Any, override

from ...util.uid import UID_SEPARATOR, Uid
from ..entity import Entity, EntityRecord
from .annotation import Annotation
from .annotation_journal import AnnotationJournal
from .annotation_record import AnnotationRecord


class UniqueAnnotation[
    T_Record: AnnotationRecord,
    T_Journal: AnnotationJournal,
](
    Annotation[T_Record, T_Journal],
):
    @classmethod
    def _calculate_parent_uid_from_dict(cls, data: Mapping[str, Any]) -> Uid:
        parent = data.get("instance_parent", data.get("instance_parent_weakref"))
        if parent is None:
            if (uid := data.get("uid")) is None or (entity := Entity.narrow_to_instance_or_none(uid)) is None:
                msg = "Either instance_parent or a uid for an existing entity must be provided."
                raise ValueError(msg)
            parent = entity.instance_parent

        if isinstance(parent, weakref.ref):
            parent = parent()

        if parent is None or not isinstance(parent, Entity):
            msg = "instance_parent must be provided and must be an Entity instance to use its UID."
            raise ValueError(msg)
        return parent.uid

    @classmethod
    @override
    def calculate_instance_name_from_dict(cls, data: Mapping[str, Any]) -> str:
        parent_uid = cls._calculate_parent_uid_from_dict(data)
        return f"{cls.__name__}@{parent_uid!s}"

    @classmethod
    @override
    def _calculate_uid(cls, data: Mapping[str, Any]) -> Uid:
        parent_uid = cls._calculate_parent_uid_from_dict(data)
        return Uid(namespace=cls.uid_namespace(), id=str(parent_uid).replace(UID_SEPARATOR, "-"))

    @classmethod
    def get[T: UniqueAnnotation](cls: type[T], entity_or_uid: Entity | EntityRecord | Uid) -> T | None:
        entity = Entity.narrow_to_instance(entity_or_uid)
        return entity.get_annotation(cls)

    @classmethod
    def get_or_create[T: UniqueAnnotation](cls: type[T], entity_or_uid: Entity | EntityRecord | Uid, /, **kwargs) -> T:
        if (annotation := cls.get(entity_or_uid)) is not None:
            annotation.journal.update(**kwargs)
            return annotation
        else:
            return cls.create(entity_or_uid, **kwargs)
