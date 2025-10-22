# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import override

from pydantic import Field

from .importer import LedgerImportData, SchemaImporter, SchemaImporterConfig


class ConfigImporterConfig(SchemaImporterConfig):
    ledgers: tuple[LedgerImportData, ...] = Field(default_factory=tuple, description="The ledgers to import")


# MARK: Importer
class ConfigImporter(SchemaImporter[ConfigImporterConfig]):
    @override
    def _do_run(self) -> None:
        with self.session(reason="Import data from configuration"):
            self._import_ledgers_from_schema(self.config.ledgers)


COMPONENT = ConfigImporter
