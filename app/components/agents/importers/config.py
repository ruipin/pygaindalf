# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from collections.abc import Sequence
from typing import override

from pydantic import Field

from ....portfolio.models.instrument import Instrument, InstrumentSchema
from ....portfolio.models.ledger import Ledger
from ....portfolio.models.transaction import Transaction, TransactionSchema
from ....util.config import BaseConfigModel
from .base import BaseImporter, BaseImporterConfig


# MARK: Configuration
class InstrumentImportSchema(BaseConfigModel, InstrumentSchema):
    pass


class TransactionImportSchema(BaseConfigModel, TransactionSchema):
    pass


class LedgerImportSchema(BaseConfigModel):
    instrument: InstrumentImportSchema = Field(description="The instrument associated with the ledger")
    transactions: Sequence[TransactionImportSchema] = Field(default_factory=list, description="The transactions to import into the ledger")


class ConfigImporterConfig(BaseImporterConfig):
    ledgers: Sequence[LedgerImportSchema] = Field(default_factory=list, description="The ledgers to import")


# MARK: Importer
class ConfigImporter(BaseImporter[ConfigImporterConfig]):
    @override
    def _do_run(self) -> None:
        with self.session(reason="Import data from configuration"):
            for ledger_data in self.config.ledgers:
                instrument = Instrument(**ledger_data.instrument.get_schema_field_values())

                transactions = set()
                for transaction_data in ledger_data.transactions:
                    transaction = Transaction(**transaction_data.get_schema_field_values())
                    transactions.add(transaction)

                ledger = Ledger(instrument=instrument, transactions=transactions)
                self.portfolio.j.add(ledger)


COMPONENT = ConfigImporter
