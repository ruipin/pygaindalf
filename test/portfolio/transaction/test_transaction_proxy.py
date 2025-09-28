# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime
from decimal import Decimal

import pytest

from app.portfolio.models.transaction.transaction import Transaction, TransactionType
from app.portfolio.models.transaction.transaction_proxy import TransactionProxy


@pytest.mark.portfolio
@pytest.mark.transaction
@pytest.mark.proxy
class TestTransactionProxy:
    def test_proxy_reuses_existing_instance_from_entity(self):
        transaction = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 1, 10),
            quantity=Decimal("10"),
            consideration=Decimal("1500"),
        )

        proxy_from_entity = transaction.proxy
        proxy_from_constructor = TransactionProxy(transaction)

        assert proxy_from_constructor is proxy_from_entity

    def test_proxy_construction_from_uid_returns_existing_proxy(self):
        transaction = Transaction(
            type=TransactionType.SELL,
            date=datetime.date(2025, 1, 12),
            quantity=Decimal("5"),
            consideration=Decimal("800"),
        )

        proxy_from_uid = TransactionProxy(transaction.uid)

        assert proxy_from_uid is transaction.proxy

    def test_proxy_forwards_attribute_access_and_uid(self):
        transaction = Transaction(
            type=TransactionType.DIVIDEND,
            date=datetime.date(2025, 2, 1),
            quantity=Decimal("0"),
            consideration=Decimal("50"),
            fees=Decimal("2"),
        )

        proxy = transaction.proxy

        assert proxy.entity is transaction
        assert proxy.uid is transaction.uid
        assert proxy.type is TransactionType.DIVIDEND
        assert proxy.date == datetime.date(2025, 2, 1)
        assert proxy.consideration == Decimal("50")
        assert proxy.fees == Decimal("2")

    def test_proxy_tracks_superseding_entity_versions(self):
        transaction = Transaction(
            type=TransactionType.BUY,
            date=datetime.date(2025, 3, 5),
            quantity=Decimal("3"),
            consideration=Decimal("450"),
        )

        proxy = transaction.proxy
        assert proxy.entity is transaction

        updated = transaction.update(quantity=Decimal("4"))

        assert proxy.entity is updated
        assert proxy.quantity == Decimal("4")