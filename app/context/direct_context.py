# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import TYPE_CHECKING, override

from .base_context import Context


if TYPE_CHECKING:
    from ..portfolio.models.portfolio import Portfolio


class DirectContext(Context):
    @property
    @override
    def portfolio(self) -> Portfolio:
        return self._runtime.portfolio_root.portfolio
