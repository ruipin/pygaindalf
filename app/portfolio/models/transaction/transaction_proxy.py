# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING

from ....util.helpers.empty_class import EmptyClass

from ..entity import EntityProxy
from .transaction import Transaction


class TransactionProxy(
    EntityProxy[Transaction],
    Transaction if TYPE_CHECKING else EmptyClass,
    init=False
):
    pass


# Register the proxy with the corresponding entity class to ensure isinstance and issubclass checks work correctly.
Transaction.register_proxy_class(TransactionProxy)