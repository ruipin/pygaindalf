# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import override

from pydantic import Field

from ....portfolio.models.annotation.forex import ForexAnnotation
from ....util.helpers.currency import Currency
from .transformer import Transformer, TransformerConfig


# MARK: Configuration
class ForexAnnotatorTransformerConfig(TransformerConfig):
    currencies: tuple[Currency, ...] = Field(default_factory=tuple, description="The target currencies for forex annotation")


# MARK: Transformer
class ForexAnnotatorTransformer(Transformer[ForexAnnotatorTransformerConfig]):
    @override
    def _do_run(self) -> None:
        with self.session(reason=f"Annotate transactions with {', '.join(c.name for c in self.config.currencies)} forex data"):
            for txn in self.context.transactions:
                ann = ForexAnnotation.get_or_create(txn)
                ann.journal.add_currency(self.config.currencies)


COMPONENT = ForexAnnotatorTransformer
