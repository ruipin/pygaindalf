# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf

from __future__ import annotations

from typing import override
from pydantic import Field

from app.portfolio.journal.entity_journal import EntityJournal
from app.portfolio.models.entity.incrementing_uid_entity import IncrementingUidEntity
from app.portfolio.models.annotation import (
    AnnotationJournal,
    IncrementingUidAnnotation,
    UniqueAnnotation,
)


class HostEntity(IncrementingUidEntity):
    """Minimal concrete entity to attach annotations to in tests."""

    # A tiny payload to ensure basic fields work; not used in assertions much
    name: str = Field(default="host")


class SampleIncrementingAnnotation(IncrementingUidAnnotation):
    """Test annotation that uses incrementing UIDs (multiple per parent)."""

    payload: int = Field(default=0)


class SampleUniqueAnnotation(UniqueAnnotation):
    """Test annotation with a UID derived from the parent UID (unique per parent)."""

    payload: int = Field(default=0)