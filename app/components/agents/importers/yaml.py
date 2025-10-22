# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import override

import yaml

from pydantic import FilePath

from .importer import PortfolioImportData, SchemaImporter, SchemaImporterConfig


class YamlImporterConfig(SchemaImporterConfig):
    filepath: FilePath


# MARK: Importer
class YamlImporter(SchemaImporter[YamlImporterConfig]):
    @override
    def _do_run(self) -> None:
        with self.session(reason=f"Import data from {self.config.filepath}"):
            yaml_data = yaml.safe_load(self.config.filepath.read_text())

            portfolio_data = PortfolioImportData.model_validate(yaml_data)

            self._import_portfolio_from_schema(portfolio_data)


COMPONENT = YamlImporter
