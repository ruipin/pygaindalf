# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref
import logging

from typing import Iterator, override, ClassVar, TYPE_CHECKING, Iterable
from collections.abc import Mapping, MutableMapping, Set, Sequence
from collections import deque

from ....util.mixins import LoggableHierarchicalMixin
from ....util.helpers import script_info
from ....util.callguard import callguard_class

from ..entity import Entity
from ..entity.entity_audit_log import EntityAuditLog
from ..entity.entity_dependents import EntityDependents
from ..uid import IncrementingUidFactory, Uid

if TYPE_CHECKING:
    from .string_uid_mapping import StringUidMapping


ENTITY_STORE_WEAKREF = False
ENTITY_AUDIT_LOG_STORE_WEAKREF = False
ENTITY_DEPENDENTS_STORE_WEAKREF = True

@callguard_class()
class EntityStore(MutableMapping[Uid, Entity], LoggableHierarchicalMixin):
    # MARK: Global instance behaviour
    if script_info.is_unit_test():
        _global_store : ClassVar[EntityStore | None] = None

        def set_as_global_store(self) -> None:
            EntityStore._global_store = self

        @staticmethod
        def clear_global_store() -> None:
            EntityStore._global_store = None

        @classmethod
        def create_global_store[T : EntityStore](cls : type[T]) -> T:
            root = cls()
            root.set_as_global_store()
            return root

    @staticmethod
    def get_global_store_or_none() -> EntityStore | None:
        from ..root import EntityRoot
        global_root = EntityRoot.get_global_root_or_none()
        if script_info.is_unit_test() and (global_store := EntityStore._global_store) is not None:
            if global_root is not None:
                raise RuntimeError("Must not have both a global EntityRoot and a global EntityStore.")
            return global_store
        if global_root is None:
            return None
        return global_root.entity_store

    @staticmethod
    def get_global_store() -> EntityStore:
        if (global_store := EntityStore.get_global_store_or_none()) is None:
            raise RuntimeError("No global EntityStore instance available.")
        return global_store


    # MARK: Initialization
    def __init__(self, *args : Entity | Mapping[Uid, Entity]):
        super().__init__()

        self._entity_store            = (dict if not ENTITY_STORE_WEAKREF            else weakref.WeakValueDictionary)()
        self._audit_log_store         = (dict if not ENTITY_AUDIT_LOG_STORE_WEAKREF  else weakref.WeakValueDictionary)()
        self._entity_dependents_store = (dict if not ENTITY_DEPENDENTS_STORE_WEAKREF else weakref.WeakValueDictionary)()

        self._uid_factory = IncrementingUidFactory()
        self._string_uid_mappings = {}

        for arg in args:
            self.update(arg)

    def reset(self):
        self._entity_store.clear()
        self._audit_log_store.clear()
        self._entity_dependents_store.clear()
        self._uid_factory.reset()
        for mapping in self._string_uid_mappings.values():
            mapping.reset()


    # MARK: UID Factory
    _uid_factory : IncrementingUidFactory

    def generate_next_uid(self, namespace : str, increment : bool = True) -> Uid:
        return self._uid_factory.next(namespace, increment=increment)


    # MARK: Name Stores
    _string_uid_mappings : MutableMapping[str, StringUidMapping]

    def get_string_uid_mapping(self, namespace : str) -> StringUidMapping:
        from .string_uid_mapping import StringUidMapping
        if (store := self._string_uid_mappings.get(namespace, None)) is None:
            store = self._string_uid_mappings[namespace] = StringUidMapping(instance_parent=self)
        return store


    # MARK: Entity Store
    _entity_store            : MutableMapping[Uid, Entity]
    _audit_log_store         : MutableMapping[Uid, EntityAuditLog]
    _entity_dependents_store : MutableMapping[Uid, EntityDependents]

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
        uid = Entity.narrow_to_uid(key)
        return self._audit_log_store.get(uid, None)

    def get_entity_dependents(self, key : Uid | Entity) -> EntityDependents | None:
        uid = Entity.narrow_to_uid(key)
        return self._entity_dependents_store.get(uid, None)


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

        self._entity_store           [uid] = entity
        self._audit_log_store        [uid] = entity.entity_log
        self._entity_dependents_store[uid] = entity.entity_dependents

    @override
    def __delitem__(self, value: Uid | Entity) -> None:
        if isinstance(value, Uid):
            uid = value
        elif isinstance(value, Entity):
            uid = value.uid
        else:
            raise TypeError(f"Value must be a Uid or Entity, got {type(value)}.")

        entity = self._entity_store.get(uid, None)
        if entity is None:
            return

        if entity.entity_log.exists:
            raise RuntimeError(f"Cannot delete entity with UID {uid} because it still exists. Call entity.delete() instead.")

        del self._entity_store[uid]

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
    def get_reachable_uids(self, roots : Uid | Iterable[Uid], *, use_journal : bool = False) -> Set[Uid]:
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

            for child in (entity.children_uids if not use_journal else entity.journal_children_uids):
                assert child in self
                if child not in reachable and child not in stack:
                    stack.append(child)

        return reachable

    def mark_and_sweep(self, roots : Uid | Iterable[Uid], *, use_journal : bool = False) -> int:
        self.log.debug(t"Mark and sweep running...")

        reachable = self.get_reachable_uids(roots, use_journal=use_journal)

        unreachable = self._entity_store.keys() - reachable

        removed = set()
        for uid in unreachable:
            entity = self._entity_store.get(uid, None)
            if entity is None:
                raise RuntimeError(f"Entity with UID {uid} not found in store during mark and sweep.")
            if entity.marked_for_deletion:
                continue

            entity.delete()

            removed.add(uid)

        n_removed = len(removed)
        self.log.debug(t"Mark and sweep completed, found {n_removed} unreachable entities: {removed}")

        return n_removed