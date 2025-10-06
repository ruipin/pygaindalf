# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from __future__ import annotations

from abc import ABCMeta
from typing import TYPE_CHECKING

from pydantic import Field

from app.portfolio.journal.journal import Journal
from app.portfolio.models.annotation.annotation_impl import AnnotationImpl
from app.portfolio.models.annotation.annotation_journal import AnnotationJournal
from app.portfolio.models.annotation.annotation_record import AnnotationRecord
from app.portfolio.models.annotation.annotation_schema import AnnotationSchema
from app.portfolio.models.annotation.incrementing_uid_annotation import IncrementingUidAnnotation
from app.portfolio.models.annotation.unique_annotation import UniqueAnnotation
from app.portfolio.models.entity import Entity, EntityImpl, EntityRecord, EntitySchemaBase, IncrementingUidMixin
from app.util.helpers.empty_class import empty_class


# --- Host entity used for annotation tests -------------------------------------------------
class HostEntitySchema(EntitySchemaBase, metaclass=ABCMeta):
    name: str = Field(default="host", description="Minimal payload field for testing annotations.")


class HostEntityImpl(
    EntityImpl,
    HostEntitySchema if TYPE_CHECKING else empty_class(),
    metaclass=ABCMeta,
):
    """Implementation mixin mirroring Production entity structure."""


class HostEntityJournal(
    HostEntityImpl,
    Journal,
    init=False,
):
    """Journal counterpart for the host entity."""


class HostEntityRecord(
    HostEntityImpl,
    EntityRecord[HostEntityJournal],
    HostEntitySchema,
    init=False,
    unsafe_hash=True,
):
    """Concrete host entity record used as a parent for annotations in tests."""


class HostEntity(
    HostEntityImpl if TYPE_CHECKING else empty_class(),
    IncrementingUidMixin,
    Entity[HostEntityRecord, HostEntityJournal],
    init=False,
    unsafe_hash=True,
):
    """Host entity wrapper that maintains the latest record snapshot automatically."""


HostEntityRecord.register_entity_class(HostEntity)


# --- Incrementing annotation ----------------------------------------------------------------
class SampleIncrementingAnnotationSchema(AnnotationSchema, metaclass=ABCMeta):
    payload: int = Field(default=0, description="Simple numeric payload tracked by the annotation.")


class SampleIncrementingAnnotationImpl(
    AnnotationImpl,
    SampleIncrementingAnnotationSchema if TYPE_CHECKING else empty_class(),
    metaclass=ABCMeta,
):
    """Implementation mixin for a test annotation with incrementing UIDs."""


class SampleIncrementingAnnotationJournal(
    SampleIncrementingAnnotationImpl,
    AnnotationJournal,
    init=False,
):
    """Journal counterpart for the incrementing annotation."""


class SampleIncrementingAnnotationRecord(
    SampleIncrementingAnnotationImpl,
    AnnotationRecord[SampleIncrementingAnnotationJournal],
    SampleIncrementingAnnotationSchema,
    init=False,
    unsafe_hash=True,
):
    """Immutable record storing annotation data for incrementing UID tests."""


class SampleIncrementingAnnotation(
    SampleIncrementingAnnotationImpl if TYPE_CHECKING else empty_class(),
    IncrementingUidAnnotation[SampleIncrementingAnnotationRecord, SampleIncrementingAnnotationJournal],
    init=False,
):
    """Annotation entity that automatically tracks its latest record and generates incrementing UIDs."""


SampleIncrementingAnnotationRecord.register_entity_class(SampleIncrementingAnnotation)


# --- Unique annotation ----------------------------------------------------------------------
class SampleUniqueAnnotationSchema(AnnotationSchema, metaclass=ABCMeta):
    payload: int = Field(default=0, description="Simple numeric payload ensuring unique annotations per parent.")


class SampleUniqueAnnotationImpl(
    AnnotationImpl,
    SampleUniqueAnnotationSchema if TYPE_CHECKING else empty_class(),
    metaclass=ABCMeta,
):
    """Implementation mixin for a unique-per-parent test annotation."""


class SampleUniqueAnnotationJournal(
    SampleUniqueAnnotationImpl,
    AnnotationJournal,
    init=False,
):
    """Journal counterpart for the unique annotation."""


class SampleUniqueAnnotationRecord(
    SampleUniqueAnnotationImpl,
    SampleUniqueAnnotationSchema if not TYPE_CHECKING else empty_class(),
    AnnotationRecord[SampleUniqueAnnotationJournal],
    init=False,
    unsafe_hash=True,
):
    """Immutable record storing annotation data for unique annotation tests."""


class SampleUniqueAnnotation(
    SampleUniqueAnnotationImpl if TYPE_CHECKING else empty_class(),
    UniqueAnnotation[SampleUniqueAnnotationRecord, SampleUniqueAnnotationJournal],
    init=False,
):
    """Annotation entity enforcing uniqueness per parent entity."""


SampleUniqueAnnotationRecord.register_entity_class(SampleUniqueAnnotation)
