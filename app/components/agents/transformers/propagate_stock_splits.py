# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import TYPE_CHECKING, override

from ....portfolio.models.transaction import Transaction
from .transformer import Transformer, TransformerConfig


if TYPE_CHECKING:
    from ....portfolio.models.ledger import Ledger


# MARK: Configuration
class PropagateStockSplitsTransformerConfig(TransformerConfig):
    pass


# MARK: Transformer
class PropagateStockSplitsTransformer(Transformer[PropagateStockSplitsTransformerConfig]):
    @override
    def _do_run(self) -> None:
        with self.session(reason="Propagate transaction splits"):
            for ledger in self.context.ledgers:
                self._process_ledger(ledger)

    def _process_ledger(self, ledger: Ledger) -> None:
        # TODO: More generic algorithm that doesn't rely on a name? E.g. online lookup

        instrument = ledger.instrument
        ticker = instrument.ticker
        if ticker is None:
            return

        parent_ledger = None

        # Parent ledger for '<TICKER> <SUFFIX>' pattern
        if " " in ticker:
            parent_ticker = ticker.split(" ", maxsplit=1)[0]
            if parent_ticker and parent_ticker != ticker:
                parent_ledger = self.context.get_ledger(ticker=parent_ticker)

        # If we found a parent ledger, we copy over stock splits
        if parent_ledger is None:
            return

        for txn in parent_ledger:
            if not txn.type.stock_split:
                continue
            self.log.debug(t"Propagating stock split transaction {txn} from '{parent_ledger}' to '{ledger}'")

            _txn = Transaction(
                type=txn.type,
                date=txn.date,
                quantity=txn.quantity,
                consideration=txn.consideration,
            )
            ledger.journal.transactions.add(_txn)


COMPONENT = PropagateStockSplitsTransformer
