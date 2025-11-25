# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Sequence

import pytest

from ..fixture import RuntimeFixture
from .lib.portfolio_validation import validate_forex_annotations


@pytest.mark.components
@pytest.mark.agents
@pytest.mark.runtime
@pytest.mark.forex
class TestForexAnnotatorTransformer:
    def _run_import_and_annotate(self, runtime: RuntimeFixture, ledgers_data: Sequence, currencies=("GBP", "USD", "JPY")) -> None:
        runtime_instance = runtime.create(
            {
                "providers": {
                    "forex": {
                        "package": "forex.oanda",
                    }
                },
                "agents": [
                    {
                        "package": "importers.config",
                        "title": "import-ledgers",
                        "ledgers": ledgers_data,
                    },
                    {
                        "package": "transformers.forex_annotator",
                        "title": "annotate-forex",
                        "currencies": currencies,
                    },
                ],
            }
        )

        runtime_instance.run()
        with runtime_instance.context:
            validate_forex_annotations(runtime_instance, list(ledgers_data), currencies=currencies)

    def test_single_gbp_instrument_mixed_usd_jpy_txns(self, runtime: RuntimeFixture) -> None:
        """GBP instrument with USD and JPY transactions across buy/sell."""
        self._run_import_and_annotate(
            runtime,
            ledgers_data=[
                {
                    "instrument": {
                        "ticker": "MIXED_GBP",
                        "type": "equity",
                        "currency": "GBP",
                    },
                    "transactions": [
                        {
                            "type": "buy",
                            "date": "2025-08-12",
                            "quantity": 10,
                            "consideration": "1000 USD",
                        },
                        {
                            "type": "sell",
                            "date": "2025-08-13",
                            "quantity": 5,
                            "consideration": "500 JPY",
                        },
                    ],
                }
            ],
        )

    def test_multiple_instruments_varied_base_currencies(self, runtime: RuntimeFixture) -> None:
        """Multiple ledgers with different instrument currencies and cross-currency txns."""
        self._run_import_and_annotate(
            runtime,
            ledgers_data=[
                {
                    "instrument": {
                        "ticker": "GBPINST",
                        "type": "equity",
                        "currency": "GBP",
                    },
                    "transactions": [
                        {
                            "type": "buy",
                            "date": "2025-09-01",
                            "quantity": 100,
                            "consideration": "10000 GBP",
                        },
                        {
                            "type": "sell",
                            "date": "2025-09-02",
                            "quantity": 40,
                            "consideration": "4000 USD",
                        },
                    ],
                },
                {
                    "instrument": {
                        "ticker": "USDINST",
                        "type": "equity",
                        "currency": "USD",
                    },
                    "transactions": [
                        {
                            "type": "buy",
                            "date": "2025-09-03",
                            "quantity": 50,
                            "consideration": "5000 USD",
                        },
                        {
                            "type": "sell",
                            "date": "2025-09-04",
                            "quantity": 20,
                            "consideration": "2200 JPY",
                        },
                    ],
                },
            ],
        )

    def test_annotations_with_subset_of_currencies(self, runtime: RuntimeFixture) -> None:
        """Request only a subset of currencies for annotation (GBP, USD)."""
        self._run_import_and_annotate(
            runtime,
            ledgers_data=[
                {
                    "instrument": {
                        "ticker": "JPY_ONLY",
                        "type": "equity",
                        "currency": "JPY",
                    },
                    "transactions": [
                        {
                            "type": "buy",
                            "date": "2025-10-10",
                            "quantity": 1000,
                            "consideration": "150000 JPY",
                        },
                        {
                            "type": "sell",
                            "date": "2025-10-11",
                            "quantity": 400,
                            "consideration": "70000 JPY",
                        },
                    ],
                }
            ],
            currencies=("GBP", "USD"),
        )
