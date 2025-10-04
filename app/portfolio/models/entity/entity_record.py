# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING

from .entity_record_base import EntityRecordBase


if TYPE_CHECKING:
    from ...journal.journal import Journal


class EntityRecord[
    T_Journal: Journal,
](
    EntityRecordBase[T_Journal],
    init=False,
    unsafe_hash=True,
):
    pass
