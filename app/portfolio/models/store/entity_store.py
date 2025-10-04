# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref

from collections import deque
from collections.abc import Iterable, Iterator, Mapping, MutableMapping
from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, ClassVar, override

from ....util.callguard import callguard_class
from ....util.helpers import script_info
from ....util.mixins import LoggableHierarchicalMixin
from ...util.uid import IncrementingUidFactory, Uid
from ..entity import Entity, EntityRecord


if TYPE_CHECKING:
    from ..entity.entity_log import EntityLog
    from .string_uid_mapping import StringUidMapping


ENTITY_LOG_STORE_WEAKREF = False
ENTITY_STORE_WEAKREF = True


@callguard_class()
class EntityStore(MutableMapping[Uid, Entity], LoggableHierarchicalMixin):
    # MARK: Global instance behaviour
    if script_info.is_unit_test():
        _global_store: ClassVar[EntityStore | None] = None

        def set_as_global_store(self) -> None:
            EntityStore._global_store = self

        @staticmethod
        def clear_global_store() -> None:
            EntityStore._global_store = None

        @classmethod
        def create_global_store[T: EntityStore](cls: type[T]) -> T:
            root = cls()
            root.set_as_global_store()
            return root

    @staticmethod
    def get_global_store_or_none() -> EntityStore | None:
        from ..root import EntityRoot

        global_root = EntityRoot.get_global_root_or_none()
        if script_info.is_unit_test() and (global_store := EntityStore._global_store) is not None:
            if global_root is not None:
                msg = "Must not have both a global EntityRoot and a global EntityStore."
                raise RuntimeError(msg)
            return global_store
        if global_root is None:
            return None
        return global_root.entity_store

    @staticmethod
    def get_global_store() -> EntityStore:
        if (global_store := EntityStore.get_global_store_or_none()) is None:
            msg = "No global EntityStore instance available."
            raise RuntimeError(msg)
        return global_store

    # MARK: Initialization
    def __init__(self, *args: Entity | Mapping[Uid, Entity]) -> None:
        super().__init__()

        # fmt: off
        self._entity_store            = (dict if not ENTITY_STORE_WEAKREF            else weakref.WeakValueDictionary)()
        self._entity_log_store        = (dict if not ENTITY_LOG_STORE_WEAKREF        else weakref.WeakValueDictionary)()
        # fmt: on

        self._uid_factory = IncrementingUidFactory()
        self._string_uid_mappings = {}

        for arg in args:
            self.update(arg)

    def reset(self) -> None:
        self._entity_log_store.clear()
        self._entity_store.clear()
        self._uid_factory.reset()
        for mapping in self._string_uid_mappings.values():
            mapping.reset()

    # MARK: UID Factory
    _uid_factory: IncrementingUidFactory

    def generate_next_uid(self, namespace: str, *, increment: bool = True) -> Uid:
        return self._uid_factory.next(namespace, increment=increment)

    # MARK: Name Stores
    _string_uid_mappings: MutableMapping[str, StringUidMapping]

    def get_string_uid_mapping(self, namespace: str) -> StringUidMapping:
        from .string_uid_mapping import StringUidMapping

        if (store := self._string_uid_mappings.get(namespace, None)) is None:
            store = self._string_uid_mappings[namespace] = StringUidMapping(instance_parent=self)
        return store

    # MARK: EntityRecord Store
    # fmt: off
    _entity_store            : MutableMapping[Uid, Entity          ]
    _entity_log_store        : MutableMapping[Uid, EntityLog       ]
    # fmt: on

    @override
    def update(self, value: Entity | Mapping[Uid, Entity], /) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        if isinstance(value, Entity):
            self[value.uid] = value
        elif isinstance(value, Mapping):
            super().update(value)
        else:
            msg = f"Value must be an EntityRecord or a Mapping[Uid, EntityRecord], got {type(value)}."
            raise TypeError(msg)

    def get_entity_log(self, key: Uid | Entity | EntityRecord) -> EntityLog | None:
        uid = key.uid if isinstance(key, (Entity, EntityRecord)) else key
        return self._entity_log_store.get(uid, None)

    def get_entity_record(self, key: Uid | Entity) -> EntityRecord | None:
        uid = key.uid if isinstance(key, Entity) else key
        entity = self.get(uid, None)
        return None if entity is None else entity.record_or_none

    # MARK: MutableMapping ABC
    @override
    def __getitem__(self, uid: Uid) -> Entity:
        if (entity := self._entity_store.get(uid, None)) is None:
            msg = f"Entity with UID {uid} not found in store."
            raise KeyError(msg)
        return entity

    @override
    def __setitem__(self, uid: Uid, entity: Entity) -> None:
        if not isinstance(uid, Uid):
            msg = f"Key {uid} is not a Uid instance."
            raise TypeError(msg)
        if not isinstance(entity, Entity):
            msg = f"Value {entity} is not an Entity instance."
            raise TypeError(msg)
        if entity.uid is not uid:
            msg = f"EntityRecord UID {entity.uid} does not match the key UID {uid}."
            raise ValueError(msg)

        self._entity_store[uid] = entity
        self._entity_log_store[uid] = entity.entity_log

    @override
    def __delitem__(self, value: Uid | Entity | EntityRecord) -> None:
        if isinstance(value, Uid):
            uid = value
        elif isinstance(value, (Entity, EntityRecord)):
            uid = value.uid
        else:
            msg = f"Value must be a Uid or EntityRecord, got {type(value)}."
            raise TypeError(msg)

        entity = self._entity_store.get(uid, None)
        if entity is None:
            return

        if entity.entity_log.exists:
            msg = f"Cannot delete entity with UID {uid} because it still exists. Call entity.delete() instead."
            raise RuntimeError(msg)

        del self._entity_store[uid]
        # We don't delete the entiy log on purpose

    @override
    def __iter__(self) -> Iterator[Uid]:  # pyright: ignore[reportIncompatibleMethodOverride] as we override MutableMapping not BaseModel
        return iter(self._entity_store)

    @override
    def __len__(self) -> int:
        return len(self._entity_store)

    @override
    def __contains__(self, value: object) -> bool:
        if isinstance(value, Uid):
            return value in self._entity_store
        elif isinstance(value, (Entity, EntityRecord)):
            return value.uid in self._entity_store
        return False

    @override
    def __str__(self) -> str:
        return str(self._entity_store)

    @override
    def __repr__(self) -> str:
        return f"EntityStore({self._entity_store!r})"

    # MARK: Garbage Collection / Reachability
    def get_reachable_uids(self, roots: Uid | Iterable[Uid], *, use_journal: bool = False) -> AbstractSet[Uid]:
        reachable = set()
        stack = deque()

        if isinstance(roots, Uid):
            stack.append(roots)
        else:
            for root in roots:
                stack.append(root)

        while stack:
            uid = stack.pop()
            if uid in reachable:
                continue
            reachable.add(uid)

            entity = self.get(uid, None)
            if entity is None:
                continue

            for child in entity.children_uids if not use_journal else entity.journal_children_uids:
                assert child in self, f"Child UID {child} of entity {entity} not found in store."
                if child not in reachable and child not in stack:
                    stack.append(child)

        return reachable

    def get_unreachable_uids(self, roots: Uid | Iterable[Uid], *, use_journal: bool = False) -> AbstractSet[Uid]:
        reachable = self.get_reachable_uids(roots, use_journal=use_journal)
        all_uids = {uid for uid, entity in self._entity_store.items() if not entity.deleted}
        return all_uids - reachable
