# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING

from ....util.helpers.empty_class import empty_class
from .entity_base import EntityBase
from .entity_record import EntityRecord
from .entity_record_base import EntityRecordBase


if TYPE_CHECKING:
    from ...journal import Journal


class Entity[  # pyright: ignore[reportIncompatibleMethodOverride, reportIncompatibleVariableOverride]
    T_Record: EntityRecord,
    T_Journal: Journal,
](
    EntityBase[T_Record, T_Journal],
    EntityRecordBase[T_Journal] if TYPE_CHECKING else empty_class(),
    init=False,
    unsafe_hash=True,
):
    pass
