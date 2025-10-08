# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime

from abc import ABCMeta
from decimal import Decimal

from iso4217 import Currency
from pydantic import Field

from ..entity import EntitySchemaBase
from .transaction_type import TransactionType


class TransactionSchema(EntitySchemaBase, metaclass=ABCMeta):
    # MARK: Fields
    # fmt: off
    type           : TransactionType = Field(description="The type of transaction.")
    date           : datetime.date   = Field(description="The date of the transaction.")
    quantity       : Decimal         = Field(description="The quantity involved in the transaction.")
    consideration  : Decimal         = Field(description="The consideration amount for the transaction.")
    fees           : Decimal         = Field(default=Decimal(0), description="The fees associated with the transaction.")
    currency       : Currency | None = Field(default=None, description="The currency in which the transaction is denominated. If not provided, it defaults to the instrument's currency.")
    # fmt: on
