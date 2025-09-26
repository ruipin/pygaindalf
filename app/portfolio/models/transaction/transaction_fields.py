# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime

from decimal import Decimal
from abc import ABCMeta
from pydantic import Field, BaseModel
from typing import TYPE_CHECKING, dataclass_transform

from ....util.helpers.empty_class import EmptyClass

from ..entity import EntityFieldsBase

from .transaction_type import TransactionType




class TransactionFields(EntityFieldsBase, metaclass=ABCMeta):
    # MARK: Fields
    type           : TransactionType = Field(description="The type of transaction.")
    date           : datetime.date   = Field(description="The date of the transaction.")
    quantity       : Decimal         = Field(description="The quantity involved in the transaction.")
    consideration  : Decimal         = Field(description="The consideration amount for the transaction.")
    fees           : Decimal         = Field(default=Decimal(0), description="The fees associated with the transaction.")