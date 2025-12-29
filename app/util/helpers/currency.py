# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from decimal import Decimal
from enum import Enum
from typing import Any

import iso4217


CURRENCIES = {
    "GBX": {
        "name": "Penny Sterling",
        "forex_alias": {
            "target": "GBP",
            "rate": Decimal("0.01"),
        },
    }
}

for currency in iso4217.Currency:
    CURRENCIES[currency.code] = {
        "name": currency.currency_name,
    }


def _update_enum_dict(locals_: dict[str, Any]) -> None:
    locals_.update({code: code for code in CURRENCIES})


class Currency(Enum):
    _update_enum_dict(locals())

    @property
    def code(self) -> str:
        return self.value

    @property
    def data(self) -> dict[str, Any]:
        return CURRENCIES[self.value]

    @property
    def currency_name(self) -> str:
        return self.data["name"]

    @property
    def _forex_alias(self) -> dict[str, Any] | None:
        return self.data.get("forex_alias", None)

    @property
    def forex_alias(self) -> Currency:
        if (alias := self._forex_alias) is None:
            return self
        else:
            return Currency(alias["target"])

    @property
    def forex_alias_rate(self) -> Decimal:
        if (alias := self._forex_alias) is None:
            return Decimal(1)
        else:
            return Decimal(alias["rate"])


S104_CURRENCY = Currency("GBP")
