# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest
from pydantic import Field
from functools import cached_property

from app.portfolio.collections.uid_proxy import UidProxySet
from app.portfolio.models.entity import IncrementingUidEntity
from app.portfolio.models.uid import Uid


# Test entities -------------------------------------------------------------
class Child(IncrementingUidEntity):
    pass

class _UidProxyChildSet(UidProxySet[Child]):
    pass

class Parent(IncrementingUidEntity):
    child_uids: set[Uid] = Field(default_factory=set)

    @cached_property
    def children(self):  # Returns a proxy set of Child entities
        return _UidProxyChildSet(owner=self, field='child_uids')


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

    def test_missing_entity_uid_raises_key_error(self):
        p = Parent()
        # Insert a raw UID not corresponding to a Child instance (fabricated namespace)
        fake = Uid(namespace=Child.uid_namespace(), id=999999)
        # Do not create entity for fake UID
        p.child_uids.add(fake)
        with pytest.raises(KeyError):
            list(p.children)  # iter should raise when resolving fake uid

