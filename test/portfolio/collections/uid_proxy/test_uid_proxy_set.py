# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from functools import cached_property
from typing import TYPE_CHECKING

import pytest

from app.portfolio.collections.uid_proxy import UidProxyMutableSet, UidProxySet
from app.portfolio.journal.journal import Journal
from app.portfolio.models.entity import Entity, EntityImpl, EntityRecord, EntitySchemaBase, IncrementingUidMixin
from app.portfolio.util.uid import Uid
from app.util.helpers.empty_class import empty_class


# Test entities -------------------------------------------------------------
class ChildSchema(EntitySchemaBase, metaclass=ABCMeta):
    pass


class ChildImpl(
    EntityImpl,
    ChildSchema if TYPE_CHECKING else empty_class(),
    metaclass=ABCMeta,
):
    pass


class ChildJournal(
    ChildImpl,
    Journal,
    init=False,
):
    pass


class ChildRecord(
    ChildImpl,
    ChildSchema if not TYPE_CHECKING else empty_class(),
    EntityRecord[ChildJournal],
    init=False,
    unsafe_hash=True,
):
    pass


class Child(
    ChildImpl if TYPE_CHECKING else empty_class(),
    IncrementingUidMixin,
    Entity[ChildRecord, ChildJournal],
    init=False,
    unsafe_hash=True,
):
    pass


ChildRecord.register_entity_class(Child)


class _UidProxyChildSet(UidProxySet[Child]):
    pass


class _UidProxyMutableChildSet(UidProxyMutableSet[Child]):
    pass


class Parent:
    child_uids: set[Uid]

    def __init__(self):
        self.child_uids = set()

    @cached_property
    def children(self):  # Returns a proxy set of Child entities
        return _UidProxyMutableChildSet(instance=self, field="child_uids")

    @cached_property
    def children_frozen(self):
        return _UidProxyChildSet(instance=self, field="child_uids")


@pytest.mark.portfolio_collections
@pytest.mark.uid_proxy_collections
class TestUidProxyMutableSet:
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
            f.add(c1)  # pyright: ignore[reportAttributeAccessIssue]
        with pytest.raises(AttributeError):
            f.discard(c1)  # pyright: ignore[reportAttributeAccessIssue]

    def test_iter_yields_entities(self):
        p = Parent()

        children = {Child() for _ in range(3)}  # pyright: ignore[reportUnhashable] as it actually is hashable...
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
        assert type(p.children) is _UidProxyMutableChildSet
        assert any(c.uid == s.uid for s in p.children_frozen)
        assert type(p.children_frozen) is _UidProxyChildSet

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
