# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pathlib import Path
from typing import override

import yaml

from pydantic import Field

from .exporter import Exporter, ExporterConfig


# MARK: Configuration
class YamlExporterConfig(ExporterConfig):
    filepath: Path = Field(description="The YAML file to export the portfolio data to")


# MARK: Exporter
class YamlExporter(Exporter[YamlExporterConfig]):
    @override
    def _do_run(self) -> None:
        dump = self.portfolio.model_dump(mode="python")

        with self.config.filepath.open("w", encoding="utf-8") as f:
            yaml.safe_dump(dump, f, sort_keys=False, allow_unicode=True)


COMPONENT = YamlExporter
