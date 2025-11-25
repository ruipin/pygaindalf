# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import override

from .base import S104BaseTransformer, S104BaseTransformerConfig


# MARK: Configuration
class S104TransformerConfig(S104BaseTransformerConfig):
    pass


# MARK: Transformer
class S104Transformer(S104BaseTransformer[S104TransformerConfig]):
    """Transformer that matches transactions in the ledgers according to S104 rules, and then calculates the S104 holdings state for each transaction."""

    @override
    def _do_run(self) -> None:
        for ledger in self.context.ledgers:
            self.process_ledger(ledger, match=True, s104_holdings=True)


COMPONENT = S104Transformer
