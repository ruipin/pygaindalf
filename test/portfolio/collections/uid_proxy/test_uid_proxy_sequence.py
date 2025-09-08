# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest
from pydantic import Field
from functools import cached_property
from decimal import Decimal
import datetime as dt

from app.portfolio.collections.uid_proxy import UidProxySequence
from app.portfolio.collections.uid_proxy.sequence import UidProxyFrozenSequence
from app.portfolio.models.entity import IncrementingUidEntity
from app.portfolio.models.transaction.transaction import Transaction, TransactionType
from app.portfolio.models.instrument.instrument import Instrument
from app.portfolio.models.uid import Uid
from iso4217 import Currency


# Proxy specialization ------------------------------------------------------
class _UidProxyTransactionSequence(UidProxySequence[Transaction]):
    pass
class _UidProxyFrozenTransactionSequence(UidProxyFrozenSequence[Transaction]):
    pass


class Holder(IncrementingUidEntity):
    transaction_uids: list[Uid] = Field(default_factory=list)

    @cached_property
    def transactions(self):
        return _UidProxyTransactionSequence(owner=self, field='transaction_uids') # type: ignore[reportAbstractUsage]

    @cached_property
    def transactions_frozen(self):
        return _UidProxyFrozenTransactionSequence(owner=self, field='transaction_uids')  # type: ignore[reportAbstractUsage]


@pytest.mark.portfolio_collections
@pytest.mark.uid_proxy_collections
class TestUidProxySequence:
    def _make_tx(self, instr, qty=1, cons=1, ttype=TransactionType.BUY):
        return Transaction(
            type=ttype,
            date=dt.date.today(),
            quantity=Decimal(qty),
            consideration=Decimal(cons),
        )

    def test_insert_and_indexing(self):
        instr = Instrument(ticker='AAPL', currency=Currency('USD'))
        h = Holder()
        t1 = self._make_tx(instr, qty=10)
        t2 = self._make_tx(instr, qty=20)

        seq = h.transactions
        assert len(seq) == 0
        seq.insert(0, t1)
        seq.insert(1, t2)
        assert len(seq) == 2
        assert seq[0] is t1 and seq[1] is t2
        assert h.transaction_uids == [t1.uid, t2.uid]

    def test_setitem_single(self):
        instr = Instrument(ticker='MSFT', currency=Currency('USD'))
        h = Holder()
        t1 = self._make_tx(instr, qty=1)
        t2 = self._make_tx(instr, qty=2)
        h.transactions.insert(0, t1)
        h.transactions[0] = t2
        assert h.transactions[0] is t2
        assert h.transaction_uids == [t2.uid]

    def test_frozen_get_and_len(self):
        instr = Instrument(ticker='META', currency=Currency('USD'))
        h = Holder()
        t1 = self._make_tx(instr, qty=4)
        h.transactions.insert(0, t1)
        f = h.transactions_frozen
        assert len(f) == 1
        assert f[0] is t1
        with pytest.raises(NotImplementedError):
            _ = f[0:1]

    def test_frozen_is_read_only(self):
        instr = Instrument(ticker='ADBE', currency=Currency('USD'))
        h = Holder()
        t1 = self._make_tx(instr, qty=1)
        h.transactions.insert(0, t1)
        f = h.transactions_frozen
        with pytest.raises(TypeError):
            f[0] = t1  # type: ignore[index]
        with pytest.raises(TypeError):
            del f[0]  # type: ignore[index]

    @pytest.mark.xfail(raises=NotImplementedError, reason="Sliced read access not implemented yet")
    def test_slice_get(self):
        instr = Instrument(ticker='TSLA', currency=Currency('USD'))
        h = Holder()
        t1 = self._make_tx(instr, qty=5)
        h.transactions.insert(0, t1)
        _ = h.transactions[0:1]

    @pytest.mark.xfail(raises=NotImplementedError, reason="Sliced write access not implemented yet")
    def test_slice_set(self):
        instr = Instrument(ticker='NVDA', currency=Currency('USD'))
        h = Holder()
        t1 = self._make_tx(instr, qty=3)
        h.transactions.insert(0, t1)
        h.transactions[0:1] = [t1]

    def test_setitem_wrong_type(self):
        instr = Instrument(ticker='ORCL', currency=Currency('USD'))
        h = Holder()
        t1 = self._make_tx(instr, qty=1)
        h.transactions.insert(0, t1)
        with pytest.raises(TypeError, match="Only single item assignment of type Transaction is allowed"):
            h.transactions[0] = 123  # type: ignore[arg-type]

    def test_repr_and_str(self):
        instr = Instrument(ticker='IBM', currency=Currency('USD'))
        h = Holder()
        t = self._make_tx(instr, qty=7)
        h.transactions.insert(0, t)

        assert any(t.uid == s.uid for s in h.transactions)
        assert type(h.transactions) == _UidProxyTransactionSequence
        assert any(t.uid == s.uid for s in h.transactions_frozen)
        assert type(h.transactions_frozen) == _UidProxyFrozenTransactionSequence
