# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import override

from .base import S104BaseTransformer, S104BaseTransformerConfig


# MARK: Configuration
class S104MatcherTransformerConfig(S104BaseTransformerConfig):
    pass


# MARK: Transformer
class S104MatcherTransformer(S104BaseTransformer[S104MatcherTransformerConfig]):
    """Transformer that matches and annotates transactions using S104 share identification rules.

    It does not calculate S104 holdings.
    """

    @override
    def _do_run(self) -> None:
        for ledger in self.context.ledgers:
            self.process_ledger(ledger, match=True, s104_holdings=False)


COMPONENT = S104MatcherTransformer
