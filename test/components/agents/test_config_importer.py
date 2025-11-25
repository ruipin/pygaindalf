# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Any

import pytest

from ..fixture import RuntimeFixture
from .lib.portfolio_validation import validate_portfolio


@pytest.mark.components
@pytest.mark.agents
@pytest.mark.runtime
@pytest.mark.importers
class TestConfigImporter:
    @staticmethod
    def _run_import_and_validate(runtime: RuntimeFixture, ledgers_data: list[dict[str, Any]]) -> None:
        runtime_instance = runtime.create(
            {
                "agents": [
                    {
                        "package": "importers.config",
                        "title": "import-ledgers",
                        "ledgers": ledgers_data,
                    }
                ]
            }
        )

        runtime_instance.run()

        validate_portfolio(runtime_instance, ledgers_data)

    def test_config_importer_single_instrument(self, runtime: RuntimeFixture) -> None:
        ledgers_data = [
            {
                "instrument": {
                    "ticker": "APPL",
                    "type": "equity",
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
                        "consideration": "10 GBP",
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
                    "type": "equity",
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
                    "type": "equity",
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
                        "consideration": "15 USD",
                    },
                ],
            },
        ]

        self._run_import_and_validate(runtime, ledgers_data)
