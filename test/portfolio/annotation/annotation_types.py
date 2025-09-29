# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from __future__ import annotations

from pydantic import Field

from app.portfolio.models.annotation import (
    IncrementingUidAnnotation,
    UniqueAnnotation,
)
from app.portfolio.models.entity.incrementing_uid_entity import IncrementingUidEntity


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
