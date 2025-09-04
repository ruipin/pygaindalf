# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import contextlib
import weakref

from typing import Iterator, override, ClassVar, TYPE_CHECKING, Iterable
from collections.abc import Mapping, MutableMapping, Set, Sequence
from collections import deque

from ....util.mixins import LoggableHierarchicalMixin
from ....util.helpers import script_info
from ....util.callguard import callguard_class

from ..entity import Entity
from ..entity.entity_audit_log import EntityAuditLog
from ..uid import IncrementingUidFactory, Uid

if TYPE_CHECKING:
    from .string_uid_mapping import StringUidMapping


ENTITY_STORE_WEAKREF = False
ENTITY_AUDIT_LOG_STORE_WEAKREF = True

@callguard_class()
class EntityStore(MutableMapping[Uid, Entity], LoggableHierarchicalMixin):
    # MARK: Global Store
    _global_store : 'ClassVar[EntityStore | None]' = None

    @staticmethod
    def get_global_store() -> 'EntityStore':
        if EntityStore._global_store is None:
            raise ValueError("Global EntityStore is not set. Please create an EntityStore instance and call make_global_store() on it before accessing the global store.")
        return EntityStore._global_store

    @staticmethod
    def get_or_create_global_store() -> 'EntityStore':
        if EntityStore._global_store is None:
            store = EntityStore()
            store.make_global_store()
            return store
        return EntityStore._global_store


    def make_global_store(self) -> None:
        EntityStore._global_store = self

    if script_info.is_unit_test():
        @staticmethod
        def reset_global_store() -> None:
            EntityStore.get_global_store().reset()


    # MARK: Initialization
    def __init__(self, *args : Entity | Mapping[Uid, Entity]):
        super().__init__()

        self._entity_store    = (dict if not ENTITY_STORE_WEAKREF           else weakref.WeakValueDictionary)()
        self._audit_log_store = (dict if not ENTITY_AUDIT_LOG_STORE_WEAKREF else weakref.WeakValueDictionary)()

        self._uid_factory = IncrementingUidFactory()
        self._string_uid_mappings = {}

        for arg in args:
            self.update(arg)

    if script_info.is_unit_test():
        def reset(self):
            self._entity_store.clear()
            self._audit_log_store.clear()
            self._uid_factory.reset()
            for mapping in self._string_uid_mappings.values():
                mapping.reset()


    # MARK: UID Factory
    _uid_factory : IncrementingUidFactory

    def generate_next_uid(self, namespace : str, increment : bool = True) -> Uid:
        return self._uid_factory.next(namespace, increment=increment)


    # MARK: Name Stores
    _string_uid_mappings : MutableMapping[str, 'StringUidMapping']

    def get_string_uid_mapping(self, namespace : str) -> 'StringUidMapping':
        from .string_uid_mapping import StringUidMapping
        if (store := self._string_uid_mappings.get(namespace, None)) is None:
            store = self._string_uid_mappings[namespace] = StringUidMapping(instance_parent=self)
        return store


    # MARK: Entity Store
    _entity_store : MutableMapping[Uid, Entity]
    _audit_log_store : MutableMapping[Uid, EntityAuditLog]

    @override
    def update(self, value : Entity | Mapping[Uid, Entity], /) -> None: # pyright: ignore[reportIncompatibleMethodOverride]
        if isinstance(value, Entity):
            self[value.uid] = value
        elif isinstance(value, Mapping):
            super().update(value)
        else:
            raise TypeError(f"Value must be an Entity or a Mapping[Uid, Entity], got {type(value)}.")

    def pop_entity(self, entity : Entity):
        if entity.uid in self._entity_store:
            del self[entity.uid]
            return entity
        return None

    def get_audit_log(self, key : Uid | Entity) -> EntityAuditLog | None:
        if isinstance(key, Entity):
            uid = key.uid
        elif isinstance(key, Uid):
            uid = key
        else:
            raise TypeError(f"Key must be a Uid or Entity, got {type(key)}.")

        return self._audit_log_store.get(uid, None)


    # MARK: MutableMapping ABC
    @override
    def __getitem__(self, uid: Uid) -> Entity:
        entity = self._entity_store[uid]
        if entity.superseded:
            raise KeyError(f"Entity with UID {uid} has been superseded and cannot be accessed.")
        return entity

    @override
    def __setitem__(self, uid: Uid, entity: Entity) -> None:
        if not isinstance(uid, Uid):
            raise TypeError(f"Key {uid} is not a Uid instance.")
        if not isinstance(entity, Entity):
            raise TypeError(f"Value {entity} is not an Entity instance.")
        if entity.uid is not uid:
            raise ValueError(f"Entity UID {entity.uid} does not match the key UID {uid}.")
        if entity.superseded:
            raise ValueError(f"Cannot add entity with UID {uid} because it has been superseded.")

        self._entity_store[uid] = entity
        self._audit_log_store[uid] = entity.entity_log

    @override
    def __delitem__(self, value: Uid | Entity) -> None:
        if isinstance(value, Uid):
            uid = value
        elif isinstance(value, Entity):
            uid = value.uid
        else:
            raise TypeError(f"Value must be a Uid or Entity, got {type(value)}.")

        del self._entity_store[uid]
        del self._audit_log_store[uid]

        for mapping in self._string_uid_mappings.values():
            mapping.remove_uid(uid)

    @override
    def __iter__(self) -> Iterator[Uid]: # pyright: ignore[reportIncompatibleMethodOverride] as we override MutableMapping not BaseModel
        return iter(self._entity_store)

    @override
    def __len__(self):
        return len(self._entity_store)

    @override
    def __contains__(self, value : object) -> bool:
        if isinstance(value, Uid):
            return value in self._entity_store
        elif isinstance(value, Entity):
            return value.uid in self._entity_store
        return False

    @override
    def __str__(self) -> str:
        return str(self._entity_store)

    @override
    def __repr__(self) -> str:
        return f"EntityStore({self._entity_store!r})"


    # MARK: Garbage Collection
    def get_reachable_uids(self, roots : Uid | Iterable[Uid]) -> Set[Uid]:
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

            for child in entity.get_child_uids():
                assert child in self
                if child not in reachable and child not in stack:
                    stack.append(child)

        return reachable

    def mark_and_sweep(self, roots : Uid | Iterable[Uid], who : str = 'system', why : str = 'mark and sweep') -> int:
        reachable = self.get_reachable_uids(roots)

        unreachable = self._entity_store.keys() - reachable

        removed = 0
        for uid in unreachable:
            entity = self.pop(uid)
            entity.entity_log.on_delete(entity, who=who, why=why)
            removed += 1

        self.log.debug("Mark and sweep completed, removed %d entities.", removed)

        return removed