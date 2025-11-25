# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Iterable
from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ....util.callguard import callguard_class
from ....util.mixins import HierarchicalMixinMinimal, LoggableMixin, NamedMixinMinimal


if TYPE_CHECKING:
    from ....util.models.uid import Uid
    from .entity import Entity
    from .entity_record import EntityRecord


# MARK: EntityRecord Dependents
@callguard_class()
class EntityDependents(LoggableMixin, HierarchicalMixinMinimal, NamedMixinMinimal):
    # MARK: EntityRecord
    _entity_uid: Uid
    _entity_version: int

    def __init__(self, uid: Uid) -> None:
        super().__init__()

        self._entity_uid = uid
        self._entity_version = 0
        self._extra_dependent_uids = set()
        self._extra_dependency_uids = frozenset()

    @classmethod
    def by_entity(cls, entity_or_record: Entity | EntityRecord) -> EntityDependents | None:
        from .entity import Entity

        entity = Entity.narrow_to_instance_or_none(entity_or_record)
        if entity is None:
            return None
        return entity.entity_dependents

    @classmethod
    def by_uid(cls, uid: Uid) -> EntityDependents | None:
        from .entity import Entity

        if (entity := Entity.by_uid_or_none(uid)) is None:
            return None
        return cls.by_entity(entity)

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

    @property
    def record_or_none(self) -> EntityRecord | None:
        from .entity_record import EntityRecord

        return EntityRecord.by_uid_or_none(self.entity_uid)

    @property
    def record(self) -> EntityRecord:
        from .entity_record import EntityRecord

        return EntityRecord.by_uid(self.entity_uid)

    # MARK: Instance name/parent
    PROPAGATE_INSTANCE_NAME_FROM_PARENT: ClassVar[bool] = False

    @property
    def instance_name(self) -> str:
        return f"{type(self).__name__}@{self.entity_uid!s}"

    @property
    def instance_parent(self) -> Entity | None:
        """Returns the parent entity of this instance, if it exists.

        If the entity does not exist in the entity store, returns None.
        """
        return self.entity_or_none

    # MARK: Pydantic schema
    @classmethod
    def __get_pydantic_core_schema__(cls, source: type[Any], handler: GetCoreSchemaHandler) -> CoreSchema:
        assert source is cls, f"Expected source to be {cls.__name__}, got {source.__name__} instead."
        return core_schema.is_instance_schema(cls)

    # MARK: Extra dependents
    _extra_dependent_uids: set[Uid]

    def add_dependent(self, entity_or_uid: Entity | EntityRecord | Uid) -> None:
        self.entity.assert_update_allowed(force_session=False)

        from .entity import Entity

        uid = Entity.narrow_to_uid(entity_or_uid)
        if uid == self.entity_uid:
            msg = "An entity cannot depend on itself."
            raise ValueError(msg)

        self._extra_dependent_uids.add(uid)

    def remove_dependent(self, entity_or_uid: Entity | EntityRecord | Uid) -> None:
        self.entity.assert_update_allowed(allow_frozen_journal=True, force_session=False)

        from .entity import Entity

        uid = Entity.narrow_to_uid(entity_or_uid)
        self._extra_dependent_uids.discard(uid)

    # MARK: Dependent Properties
    def get_dependent_uids(self, *, use_journal: bool = False) -> Iterable[Uid]:
        entity = self.entity

        if entity.is_reachable(recursive=False, use_journal=use_journal):
            if (parent := entity.record_parent_or_none) is not None:
                yield parent.uid

        yield from entity.get_children_uids(use_journal=use_journal)

        yield from self._extra_dependent_uids

    @property
    def dependent_uids(self) -> Iterable[Uid]:
        return self.get_dependent_uids()

    @property
    def dependents(self) -> Iterable[Entity]:
        from .entity import Entity

        for uid in self.dependent_uids:
            yield Entity.by_uid(uid)

    # MARK: Extra dependencies
    _extra_dependency_uids: frozenset[Uid]

    def _collect_extra_dependencies(self, record: EntityRecord) -> AbstractSet[Uid]:
        # Start with any explicitly named dependencies
        deps = None

        # Automatically detect non-children dependencies
        for uid in record.iter_field_uids(children=False, non_children=True):
            if deps is None:
                deps = set()
            deps.add(uid)

        # Optimization: If no new dependencies were found, return the declared extra dependency set directly
        if not deps:
            return record.extra_dependency_uids

        # Otherwise, merge with declared extra dependencies
        deps.update(record.extra_dependency_uids)
        return deps

    def on_delete_record(self, record: EntityRecord) -> None:
        self.log.debug(t"EntityDependents {self} received deletion notice for entity record {record}.")

        if record.uid != self.entity_uid:
            msg = f"EntityRecord UID {record.uid} does not match EntityDependents' entity UID {self.entity_uid}."
            raise ValueError(msg)
        if record.version != self._entity_version:
            msg = f"EntityRecord version has changed from {self._entity_version} to {record.version} since EntityDependents was last updated. This indicates a bug."
            raise RuntimeError(msg)

        entity = self.entity
        if (entity_version := entity.version) != self._entity_version + 1:
            msg = f"Entity {entity} version {entity.version} does not match expected version {self._entity_version + 1} after deletion of record {record}. This indicates a bug."
            raise RuntimeError(msg)
        self._entity_version = entity_version

        # Notify all extra dependencies that they can remove us from their dependents
        for uid in self._extra_dependency_uids:
            if (other := type(self).by_uid(uid)) is not None:
                other.remove_dependent(self.entity_uid)

    def on_init_record(self, record: EntityRecord) -> None:
        if record.uid != self.entity_uid:
            msg = f"EntityRecord UID {record.uid} does not match EntityDependents' entity UID {self.entity_uid}."
            raise ValueError(msg)
        if (record_version := record.version) != self._entity_version + 1:
            msg = f"EntityRecord {record} version has changed from {self._entity_version} to {record.version} since EntityDependents was last updated. This indicates a bug."
            raise RuntimeError(msg)
        self._entity_version = record_version

        # Update our extra dependencies to match the entity's current extra dependencies
        current_extra_dependencies = self._collect_extra_dependencies(record)

        # Remove dependencies that are no longer present
        for uid in self._extra_dependency_uids - current_extra_dependencies:
            if (other := type(self).by_uid(uid)) is not None:
                other.remove_dependent(self.entity_uid)

        # Add new dependencies
        for uid in current_extra_dependencies - self._extra_dependency_uids:
            if (other := type(self).by_uid(uid)) is not None:
                other.add_dependent(self.entity_uid)

        # Update our record of extra dependencies
        self._extra_dependency_uids = frozenset(current_extra_dependencies)
