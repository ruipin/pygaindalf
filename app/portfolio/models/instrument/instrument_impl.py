# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from typing import TYPE_CHECKING

from ....util.helpers.empty_class import empty_class
from ..entity import EntityImpl
from .instrument_schema import InstrumentSchema


class InstrumentImpl(
    EntityImpl,
    InstrumentSchema if TYPE_CHECKING else empty_class(),
    metaclass=ABCMeta,
):
    pass
