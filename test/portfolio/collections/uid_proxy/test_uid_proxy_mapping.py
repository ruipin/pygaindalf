# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest
from pydantic import Field
from functools import cached_property

from app.portfolio.collections.uid_proxy import UidProxyMapping
from app.portfolio.models.entity import IncrementingUidEntity
from app.portfolio.models.uid import Uid


class Item(IncrementingUidEntity):
    pass

class _UidProxyItemMapping(UidProxyMapping[str, Item]):
    pass

class Owner(IncrementingUidEntity):
    item_uids: dict[str, Uid] = Field(default_factory=dict)

    @cached_property
    def items(self):
        return _UidProxyItemMapping(owner=self, field='item_uids')


@pytest.mark.portfolio_collections
@pytest.mark.uid_proxy_collections
class TestUidProxyMapping:
    def test_set_and_get(self):
        o = Owner()
        i = Item()
        o.items['a'] = i
        assert o.items['a'] is i
        assert o.item_uids == {'a': i.uid}
        assert len(o.items) == 1
        assert list(iter(o.items)) == ['a']

    def test_del(self):
        o = Owner()
        i = Item()
        o.items['a'] = i
        del o.items['a']
        assert 'a' not in o.item_uids
        assert len(o.items) == 0

    def test_missing_key_raises_key_error(self):
        o = Owner()
        with pytest.raises(KeyError):
            _ = o.items['nope']

    def test_missing_entity_for_uid_raises(self):
        o = Owner()
        fake = Uid(namespace=Item.uid_namespace(), id=123456)
        o.item_uids['ghost'] = fake  # no Item instance created with this UID
        with pytest.raises(KeyError):
            _ = o.items['ghost']

    def test_invalid_underlying_uid_type_raises(self):
        o = Owner()
        i = Item()
        o.item_uids['good'] = i.uid
        o.item_uids['bad'] = 'not-a-uid'  # type: ignore[assignment]
        # Accessing 'bad' should TypeError due to wrong underlying type
        with pytest.raises(TypeError):
            _ = o.items['bad']

    def test_repr_and_str(self):
        o = Owner()
        i = Item()
        o.items['a'] = i

        assert any(i.uid == s.uid for s in o.items.values())
        assert type(o.items) == _UidProxyItemMapping