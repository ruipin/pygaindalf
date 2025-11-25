# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from typing import TYPE_CHECKING, override

from ....util.helpers.empty_class import empty_class
from ..transaction import Transaction
from .annotation import Annotation
from .annotation_impl import AnnotationImpl
from .annotation_journal import AnnotationJournal
from .annotation_record import AnnotationRecord
from .annotation_schema import AnnotationSchema
from .unique_annotation import UniqueAnnotation


if TYPE_CHECKING:
    from ....util.mixins import ParentType


# MARK: Implementation
class TransactionAnnotationImpl(
    AnnotationImpl,
    AnnotationSchema if TYPE_CHECKING else empty_class(),
    metaclass=ABCMeta,
):
    @property
    def transaction(self) -> Transaction:
        parent = self.entity.instance_parent
        if parent is None or not isinstance(parent, Transaction):
            msg = f"{type(self).__name__}.transaction requires parent to be a Transaction, got {type(parent)}"
            raise TypeError(msg)
        return parent


# MARK: Journal
class TransactionAnnotationJournal(
    TransactionAnnotationImpl,
    AnnotationJournal,
    init=False,
):
    pass


# MARK: Record
class TransactionAnnotationRecord[
    T_Journal: TransactionAnnotationJournal,
](
    TransactionAnnotationImpl,
    AnnotationRecord[T_Journal],
    AnnotationSchema,
    init=False,
    unsafe_hash=True,
):
    pass


# MARK: Annotation
class TransactionAnnotation[
    T_Record: TransactionAnnotationRecord,
    T_Journal: TransactionAnnotationJournal,
](
    Annotation[T_Record, T_Journal],
    metaclass=ABCMeta,
):
    @classmethod
    @override
    def _do_validate_instance_parent(cls, parent: ParentType) -> None:
        from ..transaction import Transaction

        if not isinstance(parent, Transaction):
            msg = f"{cls.__name__} requires parent to be a Transaction, got {type(parent)}"
            raise TypeError(msg)


class UniqueTransactionAnnotation[
    T_Record: TransactionAnnotationRecord,
    T_Journal: TransactionAnnotationJournal,
](
    UniqueAnnotation[T_Record, T_Journal],
    TransactionAnnotation[T_Record, T_Journal],
    metaclass=ABCMeta,
):
    @classmethod
    @override
    def _do_validate_instance_parent(cls, parent: ParentType) -> None:
        from ..transaction import Transaction

        if not isinstance(parent, Transaction):
            msg = f"{cls.__name__} requires parent to be a Transaction, got {type(parent)}"
            raise TypeError(msg)


TransactionAnnotationRecord.register_entity_class(TransactionAnnotation)
