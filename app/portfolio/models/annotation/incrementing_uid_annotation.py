# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import ABCMeta

from ..entity import IncrementingUidMixin
from .annotation import Annotation
from .annotation_journal import AnnotationJournal
from .annotation_record import AnnotationRecord


class IncrementingUidAnnotation[
    T_Record: AnnotationRecord,
    T_Journal: AnnotationJournal,
](
    IncrementingUidMixin,
    Annotation[T_Record, T_Journal],
    metaclass=ABCMeta,
):
    pass
