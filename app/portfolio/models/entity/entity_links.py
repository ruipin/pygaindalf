# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema
from typing import ClassVar, Any, TYPE_CHECKING, Iterable

from ....util.mixins import LoggableMixin, NamedMixinMinimal, HierarchicalMixinMinimal
from ....util.callguard import callguard_class

from ..uid import Uid

if TYPE_CHECKING:
    from .entity import Entity


@callguard_class()
class EntityLinks(LoggableMixin, HierarchicalMixinMinimal, NamedMixinMinimal):
    # MARK: Entity
    _entity_uid : Uid

    def __new__(cls, uid : Uid):
        from ..store import EntityStore
        if (store := EntityStore.get_global_store()) is None:
            raise ValueError(f"Could not get entity store for {cls.__name__}. The global EntityStore is not set.")
        if (instance := store.get_entity_links(uid)) is None:
            instance = super().__new__(cls)
            instance.__dict__['_entity_uid'] = uid
        return instance

    def __init__(self, uid : Uid):
        if self._entity_uid != uid:
            raise ValueError(f"EntityAuditLog UID mismatch: {self.entity_uid} != {uid}.")

        if not hasattr(self, '_dependents'):
            self._dependent_uids = set()
        if not hasattr(self, '_dependencies'):
            self._dependency_uids = set()

    @classmethod
    def from_entity(cls, entity: Entity) -> EntityLinks:
        return cls(entity.uid)

    @property
    def entity_uid(self) -> Uid:
        return self._entity_uid

    @property
    def entity(self) -> Entity | None:
        from .entity import Entity
        return Entity.by_uid(self.entity_uid)


    # MARK: Instance name/parent
    PROPAGATE_INSTANCE_NAME_FROM_PARENT : ClassVar[bool] = False

    @property
    def instance_name(self) -> str:
        return f"{self.__class__.__name__}@{str(self.entity_uid)}"

    @property
    def instance_parent(self) -> Entity | None:
        """
        Returns the parent entity of this instance, if it exists.
        If the entity does not exist in the entity store, returns None.
        """
        return self.entity


    # MARK: Pydantic schema
    @classmethod
    def __get_pydantic_core_schema__(cls, source: type[Any], handler: GetCoreSchemaHandler) -> CoreSchema:
        assert source is cls
        return core_schema.is_instance_schema(cls)


    # MARK: Generic
    def _clear(self) -> None:
        self.clear_dependents()
        self.clear_dependencies()

    def on_delete(self, entity : Entity) -> None:
        if entity.uid != self.entity_uid:
            raise ValueError(f"EntityLinks.on_delete() called with mismatched entity UID: {entity.uid} != {self.entity_uid}.")
        if entity.superseded:
            raise ValueError("EntityLinks.on_delete() called on a superseded entity.")

        # Notify all dependents
        for entity in self.dependents:
            entity.on_dependency_deleted(entity)

        # Clear all links
        self._clear()


    # MARK: Dependents
    _dependent_uids   : set[Uid]

    def add_dependent(self, other: Uid | Entity) -> None:
        uid = Entity.narrow_to_uid(other)
        if uid in self._dependent_uids:
            return
        self._dependent_uids.add(uid)

        entity = other if isinstance(other, Entity) else Entity.by_uid(uid)
        if entity is not None:
            entity.entity_links.add_dependency(self.entity_uid)

    def remove_dependent(self, other: Uid | Entity) -> None:
        uid = Entity.narrow_to_uid(other)
        if uid not in self._dependent_uids:
            return

        self._dependent_uids.remove(uid)

        entity = other if isinstance(other, Entity) else Entity.by_uid(uid)
        if entity is not None:
            entity.entity_links.remove_dependency(self.entity_uid)

    def clear_dependents(self) -> None:
        for uid in list(self._dependent_uids):
            self.remove_dependent(uid)

    @property
    def dependent_uids(self) -> Iterable[Uid]:
        entity = self.entity
        if entity is not None:
            parent = entity.instance_parent
            from .entity import Entity
            if isinstance(parent, Entity):
                yield parent.uid

        yield from self._dependent_uids

    @property
    def dependents(self) -> Iterable[Entity]:
        for uid in self._dependent_uids:
            entity = Entity.by_uid(uid)
            if entity is None:
                raise RuntimeError(f"Dependent entity with UID {uid} not found in store.")
            yield entity


    # MARK: Dependencies
    _dependency_uids : set[Uid]

    def add_dependency(self, other: Uid | Entity) -> None:
        uid = Entity.narrow_to_uid(other)
        if uid in self._dependency_uids:
            return

        self._dependency_uids.add(uid)

        entity = other if isinstance(other, Entity) else Entity.by_uid(uid)
        if entity is not None:
            entity.entity_links.add_dependent(self.entity_uid)

    def remove_dependency(self, other: Uid | Entity) -> None:
        uid = Entity.narrow_to_uid(other)
        if uid not in self._dependency_uids:
            return

        self._dependency_uids.discard(uid)

        entity = other if isinstance(other, Entity) else Entity.by_uid(uid)
        if entity is not None:
            entity.entity_links.remove_dependent(self.entity_uid)

    def clear_dependencies(self) -> None:
        for uid in list(self._dependency_uids):
            self.remove_dependency(uid)

    @property
    def dependency_uids(self) -> Iterable[Uid]:
        yield from self._dependency_uids

    @property
    def dependencies(self) -> Iterable[Entity]:
        for uid in self._dependency_uids:
            entity = Entity.by_uid(uid)
            if entity is None:
                raise RuntimeError(f"Dependency entity with UID {uid} not found in store.")
            yield entity