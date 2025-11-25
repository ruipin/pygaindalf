# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import override

from .base import S104BaseTransformer, S104BaseTransformerConfig


# MARK: Configuration
class S104HoldingsTransformerConfig(S104BaseTransformerConfig):
    pass


# MARK: Transformer
class S104HoldingsTransformer(S104BaseTransformer[S104HoldingsTransformerConfig]):
    """Transformer that calculates the S104 holdings state for each transaction in the ledgers."""

    @override
    def _do_run(self) -> None:
        for ledger in self.context.ledgers:
            self.process_ledger(ledger, match=False, s104_holdings=True)


COMPONENT = S104HoldingsTransformer
