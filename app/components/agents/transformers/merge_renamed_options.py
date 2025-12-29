# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


import re

from typing import TYPE_CHECKING, override

from ....portfolio.models.instrument import InstrumentType
from ....portfolio.models.transaction import TransactionType
from .transformer import Transformer, TransformerConfig


if TYPE_CHECKING:
    from ....portfolio.models.ledger import Ledger


# MARK: Configuration
class MergeRenamedOptionsTransformerConfig(TransformerConfig):
    pass


# MARK: Transformer
class MergeRenamedOptionsTransformer(Transformer[MergeRenamedOptionsTransformerConfig]):
    # Format: <UNDERLYING> <EXPIRY> <STRIKE> <C/P>
    OPTION_REGEX = re.compile(
        r"^(?P<underlying>\S+)\s+"
        r"(?P<expiry>\d{1,2}[A-Za-z]{3}\d{2,4})\s+"
        r"(?P<strike>\d+(?:\.\d+)?)\s+"
        r"(?P<cp>[CP])$",
        re.IGNORECASE,
    )

    @override
    def _do_run(self) -> None:
        for ledger in self.context.ledgers:
            self._process_ledger(ledger)

    def _process_ledger(self, ledger: Ledger) -> None:
        # TODO: More generic algorithm that doesn't rely on a name? E.g. online lookup

        instrument = ledger.instrument
        if instrument.type is not InstrumentType.OPTION:
            return

        # Check if the last transaction is a stock split
        if not ledger.transactions:
            return
        split_txn = ledger.transactions[-1]
        if split_txn.type is not TransactionType.SPLIT:
            return

        # Parse option ticker
        ticker = instrument.ticker
        if ticker is None:
            self.log.warning(t"Option instrument '{instrument}' has no ticker, skipping")
            return

        match = self.OPTION_REGEX.match(ticker)
        if not match:
            self.log.warning(t"Option ticker '{ticker}' does not match expected format, skipping")
            return

        # Reconstruct other option ticker based on split ratio
        underlying = match.group("underlying")
        expiry = match.group("expiry")
        strike = match.group("strike")
        cp = match.group("cp")
        ratio = split_txn.quantity
        assert ratio > 0, f"Stock split ratio must be positive, got {ratio}"
        new_strike = self.decimal(strike) / ratio
        new_ticker = f"{underlying} {expiry} {new_strike} {cp}"

        # Find other option ledger
        other_ledger = self.context.get_ledger(ticker=new_ticker)
        if other_ledger is None:
            return
        if other_ledger is ledger:
            msg = f"Option ledger '{ledger}' matched itself for ticker '{new_ticker}'"
            raise RuntimeError(msg)
        if other_ledger.instrument.type is not InstrumentType.OPTION:
            msg = f"Matched ledger '{other_ledger}' is not an option"
            raise RuntimeError(msg)

        # Sanity check: The first transaction in the other ledger should also be a matching stock split
        if not other_ledger.transactions:
            msg = f"Matched option ledger '{other_ledger}' has no transactions"
            raise RuntimeError(msg)
        other_split_txn = other_ledger.transactions[0]
        if other_split_txn.type is not TransactionType.SPLIT:
            msg = f"First transaction in matched option ledger '{other_ledger}' is not a stock split"
            raise RuntimeError(msg)
        if other_split_txn.date != split_txn.date or other_split_txn.quantity != split_txn.quantity:
            msg = f"Stock split transaction in matched option ledger '{other_ledger}' does not match original"
            raise RuntimeError(msg)

        # Merge ledgers
        merge_from = ledger
        merge_to = other_ledger
        self.log.debug(t"Merging option ledger '{merge_from}' into '{merge_to}'")

        with self.session(reason=f"Merging {merge_from} into {merge_to}"):
            for txn in merge_from.transactions:
                if txn is split_txn:
                    continue  # Skip the stock split transaction as it already exists in the target ledger

                copy = txn.copy()
                merge_to.journal.transactions.add(copy)

            self.portfolio.journal.ledgers.remove(merge_from)
            merge_from.delete()


COMPONENT = MergeRenamedOptionsTransformer
