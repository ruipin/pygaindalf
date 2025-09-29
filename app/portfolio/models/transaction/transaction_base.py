# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from typing import TYPE_CHECKING

from ....util.helpers.empty_class import EmptyClass
from ..entity import EntityBase
from .transaction_fields import TransactionFields


class TransactionBase(EntityBase, TransactionFields if TYPE_CHECKING else EmptyClass, metaclass=ABCMeta):
    pass
