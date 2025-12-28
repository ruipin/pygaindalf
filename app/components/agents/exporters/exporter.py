# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime

from abc import ABCMeta
from collections.abc import Sequence
from typing import TYPE_CHECKING, override

from pydantic import Field

from .. import Agent, AgentConfig


if TYPE_CHECKING:
    from ....portfolio.models.ledger import Ledger
    from ....portfolio.models.transaction import Transaction


# MARK: Exporter Base Configuration
class ExporterConfig(AgentConfig, metaclass=ABCMeta):
    pass


# MARK: Exporter Base class
class Exporter[C: ExporterConfig](Agent[C], metaclass=ABCMeta):
    def _should_include_transaction(self, transaction: Transaction) -> bool:  # noqa: ARG002
        return True

    def _get_transactions(self, ledger: Ledger) -> Sequence[Transaction]:
        return tuple(transaction for transaction in ledger if self._should_include_transaction(transaction))


# TODO: This could be moved to context?
# MARK: Date-filtered Exporter Configuration
class DateFilteredExporterConfig(ExporterConfig, metaclass=ABCMeta):
    start_date: datetime.date | None = Field(default=None, description="The start date for the export.")
    end_date: datetime.date | None = Field(default=None, description="The end date for the export.")


# MARK: Date-filtered Exporter Base class
class DateFilteredExporter[C: DateFilteredExporterConfig](Exporter[C], metaclass=ABCMeta):
    @override
    def _should_include_transaction(self, transaction: Transaction) -> bool:
        if not super()._should_include_transaction(transaction):
            return False

        return (not self.config.start_date or transaction.date >= self.config.start_date) and (
            not self.config.end_date or transaction.date <= self.config.end_date
        )
