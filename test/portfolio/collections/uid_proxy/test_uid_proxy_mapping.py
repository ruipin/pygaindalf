# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from functools import cached_property
from typing import TYPE_CHECKING

import pytest

from pydantic import Field

from app.portfolio.collections.uid_proxy import UidProxyMutableMapping
from app.portfolio.collections.uid_proxy.mapping import UidProxyMapping
from app.portfolio.journal.journal import Journal
from app.portfolio.models.entity import Entity, EntityImpl, EntityRecord, EntitySchemaBase, IncrementingUidMixin
from app.util.helpers.empty_class import empty_class
from app.util.models.uid import Uid


class ItemSchema(EntitySchemaBase, metaclass=ABCMeta):
    pass


class ItemImpl(
    EntityImpl,
    ItemSchema if TYPE_CHECKING else empty_class(),
    metaclass=ABCMeta,
):
    pass


class ItemJournal(
    ItemImpl,
    Journal,
    init=False,
):
    pass


class ItemRecord(
    ItemImpl,
    EntityRecord[ItemJournal],
    ItemSchema,
    init=False,
    unsafe_hash=True,
):
    pass


class Item(
    ItemImpl if TYPE_CHECKING else empty_class(),
    IncrementingUidMixin,
    Entity[ItemRecord, ItemJournal],
    init=False,
    unsafe_hash=True,
):
    pass


ItemRecord.register_entity_class(Item)


class _UidProxyItemMapping(UidProxyMutableMapping[str, Item]):
    pass


class _UidProxyFrozenItemMapping(UidProxyMapping[str, Item]):
    pass


class OwnerSchema(EntitySchemaBase, metaclass=ABCMeta):
    item_uids: dict[str, Uid] = Field(default_factory=dict)


class OwnerImpl(
    EntityImpl,
    OwnerSchema if TYPE_CHECKING else empty_class(),
    metaclass=ABCMeta,
):
    pass


class OwnerJournal(
    OwnerImpl,
    Journal,
    init=False,
):
    pass


class OwnerRecord(
    OwnerImpl,
    EntityRecord[OwnerJournal],
    OwnerSchema,
    init=False,
    unsafe_hash=True,
):
    pass


class Owner(
    OwnerImpl if TYPE_CHECKING else empty_class(),
    IncrementingUidMixin,
    Entity[OwnerRecord, OwnerJournal],
    init=False,
    unsafe_hash=True,
):
    @cached_property
    def items(self):
        return _UidProxyItemMapping(instance=self, field="item_uids")

    @cached_property
    def items_frozen(self):
        return _UidProxyFrozenItemMapping(instance=self, field="item_uids")


OwnerRecord.register_entity_class(Owner)


@pytest.mark.portfolio_collections
@pytest.mark.uid_proxy_collections
class TestUidProxyMutableMapping:
    def test_set_and_get(self):
        o = Owner()
        i = Item()
        o.items["a"] = i
        assert o.items["a"] is i
        assert o.item_uids == {"a": i.uid}
        assert len(o.items) == 1
        assert list(iter(o.items)) == ["a"]

    def test_frozen_get_and_len(self):
        o = Owner()
        i = Item()
        # populate via mutable view
        o.items["a"] = i
        f = o.items_frozen
        assert f["a"] is i
        assert len(f) == 1
        assert list(iter(f)) == ["a"]

    def test_frozen_is_read_only(self):
        o = Owner()
        i = Item()
        o.items["a"] = i
        f = o.items_frozen
        with pytest.raises(TypeError):
            f["b"] = i  # type: ignore[index]
        with pytest.raises(TypeError):
            del f["a"]  # type: ignore[index]

    def test_del(self):
        o = Owner()
        i = Item()
        o.items["a"] = i
        del o.items["a"]
        assert "a" not in o.item_uids
        assert len(o.items) == 0

    def test_missing_key_raises_key_error(self):
        o = Owner()
        with pytest.raises(KeyError):
            _ = o.items["nope"]

    def test_missing_entity_for_uid_raises(self):
        o = Owner()
        fake = Uid(namespace=Item.uid_namespace(), id=123456)
        o.item_uids["ghost"] = fake  # no Item instance created with this UID
        with pytest.raises(KeyError):
            _ = o.items["ghost"]
        with pytest.raises(KeyError):
            _ = o.items_frozen["ghost"]

    def test_invalid_underlying_uid_type_raises(self):
        o = Owner()
        i = Item()
        o.item_uids["good"] = i.uid
        o.item_uids["bad"] = "not-a-uid"  # type: ignore[assignment]
        # Accessing 'bad' should TypeError due to wrong underlying type
        with pytest.raises(TypeError):
            _ = o.items["bad"]
        with pytest.raises(TypeError):
            _ = o.items_frozen["bad"]

    def test_repr_and_str(self):
        o = Owner()
        i = Item()
        o.items["a"] = i

        assert any(i.uid == s.uid for s in o.items.values())
        assert type(o.items) is _UidProxyItemMapping
        assert any(i.uid == s.uid for s in o.items_frozen.values())
        assert type(o.items_frozen) is _UidProxyFrozenItemMapping
