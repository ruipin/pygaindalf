# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from decimal import Decimal
from typing import Any

import pytest

from ..fixture import RuntimeFixture


@pytest.mark.components
@pytest.mark.agents
@pytest.mark.runtime
@pytest.mark.portfolio
@pytest.mark.transaction
@pytest.mark.ledger
@pytest.mark.importers
class TestConfigImporter:
    @staticmethod
    def _run_import_and_validate(runtime: RuntimeFixture, ledgers_data: list[dict[str, Any]]) -> None:
        runtime_instance = runtime.create(
            {
                "components": [
                    {
                        "package": "importers.config",
                        "title": "import-ledgers",
                        "ledgers": ledgers_data,
                    }
                ]
            }
        )

        runtime_instance.run()

        portfolio = runtime_instance.context.portfolio
        ledgers_by_ticker = {ledger.instrument.ticker: ledger for ledger in portfolio}

        assert len(ledgers_by_ticker) == len(ledgers_data)

        for ledger_data in ledgers_data:
            ticker = ledger_data["instrument"]["ticker"]
            assert ticker in ledgers_by_ticker
            ledger = ledgers_by_ticker[ticker]

            for field, expected_value in ledger_data["instrument"].items():
                actual_value = getattr(ledger.instrument, field)
                if field == "currency":
                    actual_value = actual_value.code
                assert actual_value == expected_value

            transactions = list(ledger)
            transactions_data = list(ledger_data["transactions"])
            assert len(transactions) == len(transactions_data)

            for transaction in transactions:
                for transaction_data in transactions_data:
                    if transaction.type.value == transaction_data["type"] and transaction.date.isoformat() == transaction_data["date"]:
                        break
                else:
                    pytest.fail(f"No matching transaction found for {transaction!r}")
                transactions_data.remove(transaction_data)

                for field, expected_value in transaction_data.items():
                    actual_value = getattr(transaction, field)

                    if field in {"quantity", "consideration", "fees"}:
                        expected_value = Decimal(str(expected_value))
                    elif field == "currency":
                        actual_value = actual_value.code if actual_value is not None else None
                    elif field == "type":
                        actual_value = actual_value.value
                    elif field == "date":
                        actual_value = actual_value.isoformat()

                    assert actual_value == expected_value

    def test_config_importer_single_instrument(self, runtime: RuntimeFixture) -> None:
        ledgers_data = [
            {
                "instrument": {
                    "ticker": "APPL",
                    "currency": "USD",
                },
                "transactions": [
                    {
                        "type": "buy",
                        "date": "2023-01-01",
                        "quantity": 10000,
                        "consideration": 20000,
                    },
                    {
                        "type": "sell",
                        "date": "2023-01-02",
                        "quantity": 50,
                        "consideration": 15000,
                        "fees": 10,
                    },
                    {
                        "type": "sell",
                        "date": "2023-01-03",
                        "quantity": 9950,
                        "consideration": 5000,
                        "fees": 5,
                    },
                    {
                        "type": "buy",
                        "date": "2023-01-04",
                        "quantity": 100,
                        "consideration": 3000,
                    },
                    {
                        "type": "sell",
                        "date": "2023-01-05",
                        "quantity": 1000,
                        "consideration": 20000,
                        "fees": 10,
                    },
                    {
                        "type": "fee",
                        "date": "2023-01-06",
                        "quantity": 1,
                        "consideration": 10,
                        "currency": "GBP",
                    },
                ],
            }
        ]

        self._run_import_and_validate(runtime, ledgers_data)

    def test_config_importer_multiple_instruments(self, runtime: RuntimeFixture) -> None:
        ledgers_data = [
            {
                "instrument": {
                    "ticker": "APPL",
                    "currency": "USD",
                },
                "transactions": [
                    {
                        "type": "buy",
                        "date": "2023-01-01",
                        "quantity": 1000,
                        "consideration": 15000,
                    },
                    {
                        "type": "sell",
                        "date": "2023-01-05",
                        "quantity": 500,
                        "consideration": 12000,
                        "fees": 25,
                    },
                ],
            },
            {
                "instrument": {
                    "ticker": "MSFT",
                    "currency": "USD",
                },
                "transactions": [
                    {
                        "type": "buy",
                        "date": "2023-02-10",
                        "quantity": 200,
                        "consideration": 5000,
                    },
                    {
                        "type": "fee",
                        "date": "2023-02-11",
                        "quantity": 1,
                        "consideration": 15,
                        "currency": "USD",
                    },
                ],
            },
        ]

        self._run_import_and_validate(runtime, ledgers_data)
