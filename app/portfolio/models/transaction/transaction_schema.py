# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime

from abc import ABCMeta
from decimal import Decimal

from pydantic import Field

from ....util.helpers.decimal_currency import DecimalCurrency
from ..entity import EntitySchemaBase
from .transaction_type import TransactionType


class TransactionSchema(EntitySchemaBase, metaclass=ABCMeta):
    # MARK: Fields
    # fmt: off
    type           : TransactionType = Field(description="The type of transaction.")
    date           : datetime.date   = Field(description="The date of the transaction.")
    quantity       : Decimal         = Field(description="The quantity involved in the transaction.")
    consideration  : DecimalCurrency = Field(description="The consideration amount for the transaction.")
    fees           : DecimalCurrency = Field(default=DecimalCurrency(0), description="The fees associated with the transaction.")
    # fmt: on
