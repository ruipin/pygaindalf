# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from datetime import datetime
from pydantic import Field, ConfigDict, computed_field, PositiveInt, GetCoreSchemaHandler, model_validator
from pydantic_core import CoreSchema, core_schema
from enum import Enum
from collections.abc import Sequence
from typing import override, ClassVar, Any, TYPE_CHECKING, Self, Iterator, Iterable
from frozendict import frozendict
from collections.abc import Collection

from ....util.mixins import LoggableMixin, NamedMixinMinimal, HierarchicalMixinMinimal
from ....util.models import SingleInitializationModel
from ....util.callguard import callguard_class
from ....util.helpers.frozendict import FrozenDict

from ...util.uid import Uid

if TYPE_CHECKING:
    from .entity import Entity


# MARK: Entity Dependents
@callguard_class()
class EntityDependents(LoggableMixin, HierarchicalMixinMinimal, NamedMixinMinimal):
    # MARK: Entity
    _entity_uid : Uid
    _entity_version : PositiveInt

    @classmethod
    def _get_entity_dependents(cls, uid : Uid):
        from ..store import EntityStore
        if (store := EntityStore.get_global_store()) is None:
            raise ValueError(f"Could not get entity store for {cls.__name__}. The global EntityStore is not set.")
        return store.get_entity_dependents(uid)

    def __new__(cls, uid : Uid):
        if (instance := cls._get_entity_dependents(uid)) is None:
            instance = super().__new__(cls)
            instance._post_init(uid)
        return instance

    def __init__(self, uid : Uid):
        super().__init__()

    def _post_init(self, uid : Uid):
        self._entity_uid = uid
        self._entity_version = 0
        self._extra_dependent_uids = set()
        self._extra_dependency_uids = frozenset()

    @classmethod
    def by_entity(cls, entity: Entity) -> EntityDependents | None:
        return cls._get_entity_dependents(entity.uid)

    @classmethod
    def by_uid(cls, uid: Uid) -> EntityDependents | None:
        return cls._get_entity_dependents(uid)

    @property
    def entity_uid(self) -> Uid:
        return self._entity_uid

    @property
    def entity_or_none(self) -> Entity | None:
        from .entity import Entity
        return Entity.by_uid_or_none(self.entity_uid)

    @property
    def entity(self) -> Entity:
        from .entity import Entity
        return Entity.by_uid(self.entity_uid)


    # MARK: Instance name/parent
    PROPAGATE_INSTANCE_NAME_FROM_PARENT : ClassVar[bool] = False

    @property
    def instance_name(self) -> str:
        return f"{type(self).__name__}@{str(self.entity_uid)}"

    @property
    def instance_parent(self) -> Entity | None:
        """
        Returns the parent entity of this instance, if it exists.
        If the entity does not exist in the entity store, returns None.
        """
        return self.entity_or_none


    # MARK: Pydantic schema
    @classmethod
    def __get_pydantic_core_schema__(cls, source: type[Any], handler: GetCoreSchemaHandler) -> CoreSchema:
        assert source is cls
        return core_schema.is_instance_schema(cls)


    # MARK: Extra dependents
    _extra_dependent_uids : set[Uid]

    def add_dependent(self, entity_or_uid : Entity | Uid) -> None:
        if not self.entity.is_update_allowed(in_commit_only=True):
            raise RuntimeError(f"Entity {self.entity} is not allowed to be updated; cannot add dependent.")

        from .entity import Entity
        uid = Entity.narrow_to_uid(entity_or_uid)
        if uid == self.entity_uid:
            raise ValueError("An entity cannot depend on itself.")

        self._extra_dependent_uids.add(uid)

    def remove_dependent(self, entity_or_uid : Entity | Uid) -> None:
        if not self.entity.is_update_allowed(in_commit_only=True):
            raise RuntimeError(f"Entity {self.entity} is not allowed to be updated; cannot remove dependent.")

        from .entity import Entity
        uid = Entity.narrow_to_uid(entity_or_uid)
        self._extra_dependent_uids.discard(uid)


    # MARK: Dependent Properties
    def get_dependent_uids(self, *, use_journal : bool = False) -> Iterable[Uid]:
        entity = self.entity

        if entity.is_reachable(recursive=False, use_journal=use_journal):
            parent = entity.entity_parent_or_none
            if parent is not None:
                yield parent.uid

        yield from entity.get_children_uids(use_journal=use_journal)

        yield from self._extra_dependent_uids

    @property
    def dependent_uids(self) -> Iterable[Uid]:
        return self.get_dependent_uids()

    @property
    def dependents(self) -> Iterable[Entity]:
        for uid in self.dependent_uids:
            yield uid.entity


    # MARK: Extra dependencies
    _extra_dependency_uids : frozenset[Uid]

    def on_delete(self, entity : Entity) -> None:
        self.log.debug(t"EntityDependents {self} received deletion notice for entity {entity}.")

        if entity.uid != self.entity_uid:
            raise ValueError(f"Entity UID {entity.uid} does not match EntityDependents' entity UID {self.entity_uid}.")
        if entity.version != self._entity_version:
            raise RuntimeError(f"Entity version has changed from {self._entity_version} to {entity.version} since EntityDependents was last updated. This indicates a bug.")
        self._entity_version = entity.entity_log.version

        # Notify all extra dependencies that they can remove us from their dependents
        for uid in self._extra_dependency_uids:
            if (other := type(self).by_uid(uid)) is not None:
                other.remove_dependent(self.entity_uid)

    def on_init(self, entity : Entity) -> None:
        if entity.uid != self.entity_uid:
            raise ValueError(f"Entity UID {entity.uid} does not match EntityDependents' entity UID {self.entity_uid}.")
        if entity.version != self._entity_version + 1:
            raise RuntimeError(f"Entity version has changed from {self._entity_version} to {entity.version} since EntityDependents was last updated. This indicates a bug.")
        self._entity_version = entity.version

        # Update our extra dependencies to match the entity's current extra dependencies
        current_extra_dependencies = entity.extra_dependency_uids

        # Remove dependencies that are no longer present
        for uid in self._extra_dependency_uids - current_extra_dependencies:
            if (other := type(self).by_uid(uid)) is not None:
                other.remove_dependent(self.entity_uid)

        # Add new dependencies
        for uid in current_extra_dependencies - self._extra_dependency_uids:
            if (other := type(self).by_uid(uid)) is not None:
                other.add_dependent(self.entity_uid)

        # Update our record of extra dependencies
        self._extra_dependency_uids = current_extra_dependencies