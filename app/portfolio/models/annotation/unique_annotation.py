# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref

from typing import TYPE_CHECKING, Any, override

from ...util.uid import UID_SEPARATOR, Uid
from ..entity import Entity
from .annotation import Annotation
from .annotation_journal import AnnotationJournal


if TYPE_CHECKING:
    from .annotation_proxy import AnnotationProxy


class UniqueAnnotation[T_Journal: AnnotationJournal, T_Proxy: AnnotationProxy](Annotation[T_Journal, T_Proxy]):
    @classmethod
    def _calculate_parent_uid_from_dict(cls, data: dict[str, Any]) -> Uid:
        parent = data.get("instance_parent", data.get("instance_parent_weakref"))
        if isinstance(parent, weakref.ref):
            parent = parent()
        if parent is None or not isinstance(parent, Entity):
            msg = "instance_parent must be provided and must be an Entity instance to use its UID."
            raise ValueError(msg)
        return parent.uid

    @classmethod
    @override
    def calculate_instance_name_from_dict(cls, data: dict[str, Any]) -> str:
        parent_uid = cls._calculate_parent_uid_from_dict(data)
        return f"{cls.__name__}({parent_uid!s})"

    @classmethod
    @override
    def _calculate_uid(cls, data: dict[str, Any]) -> Uid:
        parent_uid = cls._calculate_parent_uid_from_dict(data)
        return Uid(namespace=cls.uid_namespace(), id=str(parent_uid).replace(UID_SEPARATOR, "-"))
