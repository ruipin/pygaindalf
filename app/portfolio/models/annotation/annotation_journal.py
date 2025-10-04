# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from ...journal.journal import Journal
from .annotation_impl import AnnotationImpl


class AnnotationJournal(
    AnnotationImpl,
    Journal,
    init=False,
):
    pass
