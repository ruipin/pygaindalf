# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from functools import cached_property

from collections.abc import Set
from abc import abstractmethod, ABCMeta
from typing import Iterable, TYPE_CHECKING

from ....util.callguard import callguard_class
from ..uid import Uid
from .superseded import superseded_check


if TYPE_CHECKING:
    from .entity import Entity
    from ..annotation import Annotation


@callguard_class(
    decorator=superseded_check, decorate_public_methods=True
)
class EntityBase[T_Uid_Set : Set[Uid]](metaclass=ABCMeta):
    # MARK: Annotations
    if TYPE_CHECKING:
        annotation_uids : T_Uid_Set

    def get_annotations[T : Annotation](self, cls : type[T]) -> Iterable[T]:
        from ..annotation import Annotation
        for uid in self.annotation_uids:
            annotation = Annotation.narrow_to_entity(uid)
            if not isinstance(annotation, cls):
                continue
            yield annotation

    def get_annotation_uids(self, cls : type[Annotation]) -> Iterable[Uid]:
        for annotation in self.get_annotations(cls):
            yield annotation.uid



    # MARK: Entity Dependencies
    if TYPE_CHECKING:
        extra_dependency_uids : T_Uid_Set