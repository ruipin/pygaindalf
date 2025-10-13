# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import override

from pydantic import Field

from ....portfolio.models.instrument import Instrument, InstrumentSchema
from ....portfolio.models.ledger import Ledger
from ....portfolio.models.transaction import Transaction, TransactionSchema
from ....util.config import BaseConfigModel
from .importer import Importer, ImporterConfig


# MARK: Configuration
class InstrumentImportSchema(BaseConfigModel, InstrumentSchema):
    pass


class TransactionImportSchema(BaseConfigModel, TransactionSchema):
    pass


class LedgerImportSchema(BaseConfigModel):
    instrument: InstrumentImportSchema = Field(description="The instrument associated with the ledger")
    transactions: tuple[TransactionImportSchema, ...] = Field(default_factory=tuple, description="The transactions to import into the ledger")


class ConfigImporterConfig(ImporterConfig):
    ledgers: tuple[LedgerImportSchema, ...] = Field(default_factory=tuple, description="The ledgers to import")


# MARK: Importer
class ConfigImporter(Importer[ConfigImporterConfig]):
    @override
    def _do_run(self) -> None:
        with self.session(reason="Import data from configuration"):
            for ledger_data in self.config.ledgers:
                instrument = Instrument(**ledger_data.instrument.get_schema_field_values())

                transactions = set()
                for transaction_data in ledger_data.transactions:
                    transaction = Transaction(**transaction_data.get_schema_field_values(by_alias=True))
                    transactions.add(transaction)

                ledger = Ledger(instrument=instrument, transactions=transactions)
                self.portfolio.j.add(ledger)


COMPONENT = ConfigImporter
