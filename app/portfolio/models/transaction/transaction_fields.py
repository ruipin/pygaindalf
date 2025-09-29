# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime

from abc import ABCMeta
from decimal import Decimal

from pydantic import Field

from ..entity import EntityFieldsBase
from .transaction_type import TransactionType


class TransactionFields(EntityFieldsBase, metaclass=ABCMeta):
    # MARK: Fields
    # fmt: off
    type           : TransactionType = Field(description="The type of transaction.")
    date           : datetime.date   = Field(description="The date of the transaction.")
    quantity       : Decimal         = Field(description="The quantity involved in the transaction.")
    consideration  : Decimal         = Field(description="The consideration amount for the transaction.")
    fees           : Decimal         = Field(default=Decimal(0), description="The fees associated with the transaction.")
    # fmt: on
