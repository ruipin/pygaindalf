# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from typing import TYPE_CHECKING

from ....util.helpers.empty_class import EmptyClass

from ..entity import EntityBase

from .instrument_fields import InstrumentFields


class InstrumentBase(EntityBase, InstrumentFields if TYPE_CHECKING else EmptyClass, metaclass=ABCMeta):
    pass