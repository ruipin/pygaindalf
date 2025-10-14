# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta

from iso4217 import Currency
from pydantic import Field

from ..entity import EntitySchemaBase


class InstrumentSchema(EntitySchemaBase, metaclass=ABCMeta):
    # MARK: Fields
    isin: str | None = Field(
        default=None, min_length=1, exclude_if=lambda v: v is None, description="International Securities Identification Number (ISIN) of the instrument."
    )
    ticker: str | None = Field(
        default=None, min_length=1, exclude_if=lambda v: v is None, description="Ticker symbol of the instrument, used for trading and identification."
    )
    currency: Currency = Field(description="The currency in which the instrument is denominated.")
