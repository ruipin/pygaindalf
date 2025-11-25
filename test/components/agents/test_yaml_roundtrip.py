# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from ..fixture import RuntimeFixture
from .lib.portfolio_validation import validate_portfolio


if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.components
@pytest.mark.agents
@pytest.mark.runtime
@pytest.mark.importers
@pytest.mark.exporters
class TestYamlRoundtrip:
    @staticmethod
    def _portfolio_expectations() -> list[dict[str, Any]]:
        return [
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
                        "quantity": 100,
                        "consideration": 2000,
                    },
                    {
                        "type": "sell",
                        "date": "2023-01-02",
                        "quantity": 40,
                        "consideration": 900,
                        "fees": 5,
                    },
                    {
                        "type": "fee",
                        "date": "2023-01-03",
                        "quantity": 1,
                        "consideration": "10 GBP",
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
                        "quantity": 50,
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

    def test_yaml_import_export_roundtrip(self, runtime: RuntimeFixture, tmp_path: Path) -> None:
        export_path = tmp_path / "portfolio.yaml"

        # First runtime: import via config importer, then export to YAML
        ledgers_data = self._portfolio_expectations()

        runtime_import_export = runtime.create(
            {
                "agents": [
                    {
                        "package": "importers.config",
                        "title": "import-ledgers",
                        "ledgers": ledgers_data,
                    },
                    {
                        "package": "exporters.yaml",
                        "title": "export-portfolio-yaml",
                        "filepath": str(export_path),
                    },
                ]
            }
        )

        runtime_import_export.run()

        assert export_path.exists()

        # Second runtime: import from the exported YAML file
        runtime_yaml_import = runtime.create(
            {
                "agents": [
                    {
                        "package": "importers.yaml",
                        "title": "import-portfolio-yaml",
                        "filepath": str(export_path),
                    }
                ]
            }
        )

        runtime_yaml_import.run()

        # Validate that the portfolio matches the original expectations
        validate_portfolio(runtime_yaml_import, ledgers_data)
