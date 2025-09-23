# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref
from typing import override, Any, Self

from ..entity import Entity
from ..uid import Uid, UID_SEPARATOR

from .annotation_journal import AnnotationJournal
from .annotation import Annotation


class UniqueAnnotation[T_Journal : AnnotationJournal](Annotation[T_Journal]):
    @classmethod
    def _calculate_parent_uid_from_dict(cls, data : dict[str, Any]) -> Uid:
        parent = data.get('instance_parent', data.get('instance_parent_weakref', None))
        if isinstance(parent, weakref.ref):
            parent = parent()
        if parent is None or not isinstance(parent, Entity):
            raise ValueError("instance_parent must be provided and must be an Entity instance to use its UID.")
        return parent.uid

    @classmethod
    @override
    def calculate_instance_name_from_dict(cls, data : dict[str, Any]) -> str:
        parent_uid = cls._calculate_parent_uid_from_dict(data)
        return f"{cls.__name__}({str(parent_uid)})"

    @classmethod
    @override
    def _calculate_uid(cls, data : dict[str, Any]) -> Uid:
        parent_uid = cls._calculate_parent_uid_from_dict(data)
        return Uid(namespace=cls.uid_namespace(), id=str(parent_uid).replace(UID_SEPARATOR, '-'))