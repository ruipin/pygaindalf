# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Set
from abc import ABCMeta
from typing import Iterable, TYPE_CHECKING

from ....util.callguard import callguard_class
from ....util.helpers.empty_class import EmptyClass
from ..uid import Uid
from .superseded import superseded_check
from .entity_fields import EntityFields


if TYPE_CHECKING:
    from ..annotation import Annotation


# MARK: Base
@callguard_class(
    decorator=superseded_check, decorate_public_methods=True
)
class EntityBase[T_Uid_Set : Set[Uid]](EntityFields[T_Uid_Set] if TYPE_CHECKING else EmptyClass, metaclass=ABCMeta):
    # MARK: Annotations
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