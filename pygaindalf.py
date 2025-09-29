# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""Main entry point for the pygaindalf CLI application.

Initializes logging and configuration, parses CLI arguments, and executes commands.
"""

from app.config import CFG
from app.util.logging import getLogger


def main() -> None:
    CFG.initialize()

    cls = CFG.providers["oanda"].component_class
    oanda = cls(CFG.providers["oanda"])

    import datetime

    from_currency = "USD"
    to_currency = "EUR"
    date = datetime.datetime.now(tz=datetime.UTC).date() - datetime.timedelta(days=1)
    rate = oanda.get_daily_rate(from_currency, to_currency, date)
    getLogger("main").info(f"{from_currency}->{to_currency} exchange rate for {date}: {rate}")

    amount = 100
    converted = oanda.convert_currency(amount, from_currency, to_currency, date)
    getLogger("main").info(f"Converted {amount} {from_currency} to {converted} {to_currency} on {date}")


if __name__ == "__main__":
    main()
