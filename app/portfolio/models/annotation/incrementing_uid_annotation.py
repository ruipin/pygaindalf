# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import ABCMeta

from ..entity import IncrementingUidEntityMixin

from .annotation_journal import AnnotationJournal
from .annotation import Annotation


class IncrementingUidAnnotation[T_Journal : AnnotationJournal](IncrementingUidEntityMixin, Annotation[T_Journal], metaclass=ABCMeta):
    pass