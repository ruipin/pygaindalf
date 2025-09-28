# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import ABCMeta
from typing import TYPE_CHECKING

from ..entity import IncrementingUidEntityMixin

from .annotation_journal import AnnotationJournal
from .annotation import Annotation

if TYPE_CHECKING:
    from .annotation_proxy import AnnotationProxy


class IncrementingUidAnnotation[T_Journal : AnnotationJournal, T_Proxy : AnnotationProxy](IncrementingUidEntityMixin, Annotation[T_Journal, T_Proxy], metaclass=ABCMeta):
    pass