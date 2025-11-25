# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import override

import yaml

from pydantic import Field

from ....util.config.models.env_path import EnvForceNewPath
from .exporter import Exporter, ExporterConfig


# MARK: Configuration
class YamlExporterConfig(ExporterConfig):
    filepath: EnvForceNewPath = Field(description="The YAML file to export the portfolio data to")


# MARK: Exporter
class YamlExporter(Exporter[YamlExporterConfig]):
    @override
    def _do_run(self) -> None:
        dump = self.portfolio.model_dump(mode="json", exclude_none=True, exclude_defaults=True)

        with self.config.filepath.open("w", encoding="utf-8") as f:
            yaml.safe_dump(dump, f, sort_keys=False, allow_unicode=True)


COMPONENT = YamlExporter
