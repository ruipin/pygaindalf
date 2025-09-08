# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest
from pydantic import Field
from functools import cached_property

from app.portfolio.collections.uid_proxy import UidProxySet
from app.portfolio.collections.uid_proxy.set.set import UidProxyFrozenSet
from app.portfolio.models.entity import IncrementingUidEntity
from app.portfolio.models.uid import Uid


# Test entities -------------------------------------------------------------
class Child(IncrementingUidEntity):
    pass

class _UidProxyChildSet(UidProxySet[Child]):
    pass
class _UidProxyFrozenChildSet(UidProxyFrozenSet[Child]):
    pass

class Parent(IncrementingUidEntity):
    child_uids: set[Uid] = Field(default_factory=set)

    @cached_property
    def children(self):  # Returns a proxy set of Child entities
        return _UidProxyChildSet(owner=self, field='child_uids')

    @cached_property
    def children_frozen(self):
        return _UidProxyFrozenChildSet(owner=self, field='child_uids')


@pytest.mark.portfolio_collections
@pytest.mark.uid_proxy_collections
class TestUidProxySet:
    def test_add_and_contains_and_len(self):
        p = Parent()
        c1, c2 = Child(), Child()

        proxy = p.children
        assert len(proxy) == 0
        assert c1 not in proxy

        proxy.add(c1)
        proxy.add(c2)
        assert len(proxy) == 2
        assert c1 in proxy and c2 in proxy
        # Underlying storage holds Uids only
        assert p.child_uids == {c1.uid, c2.uid}

    def test_discard(self):
        p = Parent()
        c1, c2 = Child(), Child()
        proxy = p.children
        proxy.add(c1)
        proxy.add(c2)
        proxy.discard(c1)
        assert len(proxy) == 1
        assert c1 not in proxy and c2 in proxy
        assert p.child_uids == {c2.uid}

    def test_frozen_contains_iter_and_read_only(self):
        p = Parent()
        c1, c2 = Child(), Child()
        p.children.add(c1)
        p.children.add(c2)
        f = p.children_frozen
        assert len(f) == 2
        assert c1 in f and c2 in f
        assert {x.uid for x in f} == {c1.uid, c2.uid}
        with pytest.raises(AttributeError):
            f.add(c1)  # type: ignore[attr-defined]
        with pytest.raises(AttributeError):
            f.discard(c1)  # type: ignore[attr-defined]

    def test_iter_yields_entities(self):
        p = Parent()

        children = set(Child() for _ in range(3))
        for ch in children:
            p.children.add(ch)

        # Iteration returns the actual Child objects
        got = set(iter(p.children))
        assert got == children
        assert {c.uid for c in got} == {c.uid for c in children}

    def test_repr_and_str(self):
        p = Parent()
        c = Child()
        p.children.add(c)

        assert any(c.uid == s.uid for s in p.children)
        assert type(p.children) == _UidProxyChildSet
        assert any(c.uid == s.uid for s in p.children_frozen)
        assert type(p.children_frozen) == _UidProxyFrozenChildSet

    def test_missing_entity_uid_raises_key_error(self):
        p = Parent()
        # Insert a raw UID not corresponding to a Child instance (fabricated namespace)
        fake = Uid(namespace=Child.uid_namespace(), id=999999)
        # Do not create entity for fake UID
        p.child_uids.add(fake)
        with pytest.raises(KeyError):
            list(p.children)  # iter should raise when resolving fake uid
        with pytest.raises(KeyError):
            list(p.children_frozen)

