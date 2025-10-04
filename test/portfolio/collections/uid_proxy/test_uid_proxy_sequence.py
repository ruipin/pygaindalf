# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime as dt

from abc import ABCMeta
from decimal import Decimal
from functools import cached_property
from typing import TYPE_CHECKING

import pytest

from pydantic import Field

from app.portfolio.collections.uid_proxy import UidProxyMutableSequence
from app.portfolio.collections.uid_proxy.sequence import UidProxySequence
from app.portfolio.journal.journal import Journal
from app.portfolio.models.entity import Entity, EntityImpl, EntityRecord, EntitySchemaBase, IncrementingUidMixin
from app.portfolio.models.transaction import Transaction, TransactionType
from app.portfolio.util.uid import Uid
from app.util.helpers.empty_class import empty_class


# Proxy specialization ------------------------------------------------------
class _UidProxyTransactionSequence(UidProxyMutableSequence[Transaction]):
    pass


class _UidProxyFrozenTransactionSequence(UidProxySequence[Transaction]):
    pass


class HolderSchema(EntitySchemaBase, metaclass=ABCMeta):
    transaction_uids: list[Uid] = Field(default_factory=list)


class HolderImpl(
    EntityImpl,
    HolderSchema if TYPE_CHECKING else empty_class(),
    metaclass=ABCMeta,
):
    pass


class HolderJournal(
    HolderImpl,
    Journal,
    init=False,
):
    pass


class HolderRecord(
    HolderImpl,
    HolderSchema if not TYPE_CHECKING else empty_class(),
    EntityRecord[HolderJournal],
    init=False,
    unsafe_hash=True,
):
    pass


class Holder(
    HolderImpl if TYPE_CHECKING else empty_class(),
    IncrementingUidMixin,
    Entity[HolderRecord, HolderJournal],
    init=False,
    unsafe_hash=True,
):
    @cached_property
    def transactions(self):
        return _UidProxyTransactionSequence(instance=self, field="transaction_uids")

    @cached_property
    def transactions_frozen(self):
        return _UidProxyFrozenTransactionSequence(instance=self, field="transaction_uids")


HolderRecord.register_entity_class(Holder)


@pytest.mark.portfolio_collections
@pytest.mark.uid_proxy_collections
class TestUidProxyMutableSequence:
    def _make_tx(self, qty=1, cons=1, ttype=TransactionType.BUY):
        return Transaction(
            type=ttype,
            date=dt.datetime.now(tz=dt.UTC).date(),
            quantity=Decimal(qty),
            consideration=Decimal(cons),
        )

    def test_insert_and_indexing(self):
        h = Holder()
        t1 = self._make_tx(qty=10)
        t2 = self._make_tx(qty=20)

        seq = h.transactions
        assert len(seq) == 0
        seq.insert(0, t1)
        seq.insert(1, t2)
        assert len(seq) == 2
        assert seq[0] is t1 and seq[1] is t2
        assert h.transaction_uids == [t1.uid, t2.uid]

    def test_setitem_single(self):
        h = Holder()
        t1 = self._make_tx(qty=1)
        t2 = self._make_tx(qty=2)
        h.transactions.insert(0, t1)
        h.transactions[0] = t2
        assert h.transactions[0] is t2
        assert h.transaction_uids == [t2.uid]

    def test_frozen_get_and_len(self):
        h = Holder()
        t1 = self._make_tx(qty=4)
        h.transactions.insert(0, t1)
        f = h.transactions_frozen
        assert len(f) == 1
        assert f[0] is t1
        with pytest.raises(NotImplementedError):
            _ = f[0:1]

    def test_frozen_is_read_only(self):
        h = Holder()
        t1 = self._make_tx(qty=1)
        h.transactions.insert(0, t1)
        f = h.transactions_frozen
        with pytest.raises(TypeError):
            f[0] = t1  # type: ignore[index]
        with pytest.raises(TypeError):
            del f[0]  # type: ignore[index]

    @pytest.mark.xfail(raises=NotImplementedError, reason="Sliced read access not implemented yet")
    def test_slice_get(self):
        h = Holder()
        t1 = self._make_tx(qty=5)
        h.transactions.insert(0, t1)
        _ = h.transactions[0:1]

    @pytest.mark.xfail(raises=NotImplementedError, reason="Sliced write access not implemented yet")
    def test_slice_set(self):
        h = Holder()
        t1 = self._make_tx(qty=3)
        h.transactions.insert(0, t1)
        h.transactions[0:1] = [t1]

    def test_setitem_wrong_type(self):
        h = Holder()
        t1 = self._make_tx(qty=1)
        h.transactions.insert(0, t1)
        with pytest.raises(TypeError, match="Expected Transaction, got int"):
            h.transactions[0] = 123  # type: ignore[arg-type]

    def test_repr_and_str(self):
        h = Holder()
        t = self._make_tx(qty=7)
        h.transactions.insert(0, t)

        assert any(t.uid == s.uid for s in h.transactions)
        assert type(h.transactions) is _UidProxyTransactionSequence
        assert any(t.uid == s.uid for s in h.transactions_frozen)
        assert type(h.transactions_frozen) is _UidProxyFrozenTransactionSequence
