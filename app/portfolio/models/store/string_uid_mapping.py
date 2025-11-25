# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from collections.abc import Iterator, Mapping, MutableMapping
from typing import TYPE_CHECKING, override

from app.portfolio.models.store.entity_store import EntityStore

from ....util.callguard import callguard_class
from ....util.helpers import script_info
from ....util.mixins import LoggableHierarchicalMixin
from ....util.models.uid import Uid
from ..entity import Entity


if TYPE_CHECKING:
    from ..entity import EntityRecord
    from .entity_store import EntityStore


@callguard_class()
class StringUidMapping(MutableMapping[str, Uid], LoggableHierarchicalMixin):
    # MARK: Initialization
    def __init__(self, /, *args: Mapping[str, Entity] | Mapping[str, Uid], instance_parent: EntityStore | None = None) -> None:
        super().__init__(instance_parent=instance_parent)

        self._store = {}
        self._reverse = {}

        for arg in args:
            self.update(arg)

    if script_info.is_unit_test():

        def reset(self) -> None:
            self._store.clear()

    @property
    def entity_store(self) -> EntityStore:
        from .entity_store import EntityStore

        parent = self.instance_parent
        if parent is None or not isinstance(parent, EntityStore):
            msg = "InstanceNameStore must have an EntityStore as parent."
            raise ValueError(msg)
        return parent

    # MARK: Name Store
    _store: MutableMapping[str, Uid]
    _reverse: MutableMapping[Uid, str]

    @override
    def update(self, value: Mapping[str, Uid | Entity], /) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        if isinstance(value, Mapping):
            for name, item in value.items():
                if not isinstance(name, str):
                    msg = f"Key {name} is not a str instance."
                    raise TypeError(msg)
                if isinstance(item, Uid):
                    self[name] = item
                elif isinstance(item, Entity):
                    self[name] = item.uid
                else:
                    msg = f"Value must be an EntityRecord or a Uid, got {type(item)}."
                    raise TypeError(msg)
        else:
            msg = f"Value must be a Mapping, got {type(value)}."
            raise TypeError(msg)

    def get_entity(self, name: str, *, fail: bool = True) -> Entity | None:
        uid = self._store.get(name, None)
        if uid is None:
            if fail:
                msg = f"No entity found with name '{name}'."
                raise KeyError(msg)
            return None

        return self.entity_store.get(uid, None)

    def get_entity_record(self, name: str, *, fail: bool = True) -> EntityRecord | None:
        entity = self.get_entity(name, fail=fail)
        return None if entity is None else entity.record_or_none

    def remove_uid(self, uid: Uid) -> None:
        name = self._reverse.pop(uid, None)
        if name is not None:
            self._store.pop(name, None)

    # MARK: MutableMapping ABC
    @override
    def __getitem__(self, name: str) -> Uid:
        return self._store[name]

    @override
    def __setitem__(self, name: str, uid: Uid) -> None:
        if not isinstance(name, str):
            msg = f"Key {name} is not a str instance."
            raise TypeError(msg)
        if not isinstance(uid, Uid):
            msg = f"Value {uid} is not a Uid instance."
            raise TypeError(msg)
        existing = self._store.get(name, None)
        if existing is not None:
            if existing != uid:
                msg = f"Name '{name}' is already mapped to UID {existing}, cannot remap to {uid}."
                raise ValueError(msg)
        else:
            self._store[name] = uid
            self._reverse[uid] = name

    @override
    def __delitem__(self, value: str) -> None:
        if isinstance(value, str):
            uid = self.pop(value)
            del self._reverse[uid]
        else:
            msg = f"Value must be a str, Uid or EntityRecord, got {type(value)}."
            raise TypeError(msg)

    @override
    def __iter__(self) -> Iterator[str]:
        return iter(self._store)

    @override
    def __len__(self) -> int:
        return len(self._store)

    @override
    def __contains__(self, value: object) -> bool:
        if isinstance(value, str):
            return value in self._store
        return False

    @override
    def __str__(self) -> str:
        return str(self._store)

    @override
    def __repr__(self) -> str:
        return f"StringUidMapping({self._store!r})"
