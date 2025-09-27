# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from pydantic import Field
from iso4217 import Currency

from ..entity import EntityFieldsBase


class InstrumentFields(EntityFieldsBase, metaclass=ABCMeta):
    # MARK: Fields
    isin     : str | None = Field(default=None, min_length=1, description="International Securities Identification Number (ISIN) of the instrument.")
    ticker   : str | None = Field(default=None, min_length=1, description="Ticker symbol of the instrument, used for trading and identification.")
    currency : Currency   = Field(description="The currency in which the instrument is denominated.")

