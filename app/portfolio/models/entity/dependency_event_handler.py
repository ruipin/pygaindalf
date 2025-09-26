# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import dataclasses

from typing import TYPE_CHECKING, Protocol, Iterable, Sequence, Callable, Set, overload, Literal, Any, runtime_checkable, override
from pydantic import InstanceOf, ConfigDict
from enum import StrEnum

from ....util.models import LoggableModel


if TYPE_CHECKING:
    from .entity import Entity
    from ...journal import EntityJournal


# MARK: Enums
class EntityDependencyEventType(StrEnum):
    UPDATED = 'updated'
    DELETED = 'deleted'

    @property
    def updated(self) -> bool:
        return self is EntityDependencyEventType.UPDATED

    @property
    def deleted(self) -> bool:
        return self is EntityDependencyEventType.DELETED


# MARK: Protocols
@runtime_checkable
class EntityDependencyEventEntityMatcher(Protocol):
    @staticmethod
    def __call__(self : Entity, entity: Entity) -> bool: ... # pyright: ignore[reportSelfClsParameterName]

@runtime_checkable
class EntityDependencyEventAttributeMatcher(Protocol):
    @staticmethod
    def __call__(self : Entity, attribute: str, value : Any) -> bool: ... # pyright: ignore[reportSelfClsParameterName]

@runtime_checkable
class EntityDependencyEventHandler(Protocol):
    @staticmethod
    def __call__(self : Entity, event : EntityDependencyEventType, entity: Entity, *, matched_attributes : frozenset[str] | None = None) -> None: ... # pyright: ignore[reportSelfClsParameterName]


# MARK: Record
class EntityDependencyEventHandlerRecord(LoggableModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
    )

    handler            : InstanceOf[EntityDependencyEventHandler]
    on_updated         : bool
    on_deleted         : bool
    entity_matchers    : tuple[InstanceOf[EntityDependencyEventEntityMatcher   ]      , ...] | InstanceOf[EntityDependencyEventEntityMatcher   ]       | None = None
    attribute_matchers : tuple[InstanceOf[EntityDependencyEventAttributeMatcher] | str, ...] | InstanceOf[EntityDependencyEventAttributeMatcher] | str | None = None

    def register(self, owner : type[Entity]) -> None:
        owner.register_dependency_event_handler(self)


    # MARK: Matching
    def match_event(self, event : EntityDependencyEventType) -> bool:
        if event.updated and self.on_updated:
            return True
        if event.deleted and self.on_deleted:
            return True
        return False

    def match_entity(self, owner : Entity, event : EntityDependencyEventType, entity : Entity) -> bool:
        if self.entity_matchers is None:
            return True

        if isinstance(self.entity_matchers, Callable):
            return self.entity_matchers(owner, entity)

        for matcher in self.entity_matchers:
            if matcher(owner, entity):
                return True
        return False

    def match_attribute(self, owner : Entity, attribute : str, value : Any) -> bool:
        if self.attribute_matchers is None:
            return True

        if isinstance(self.attribute_matchers, Callable):
            return self.attribute_matchers(owner, attribute, value)
        if isinstance(self.attribute_matchers, str):
            return self.attribute_matchers == attribute

        for matcher in self.attribute_matchers:
            if isinstance(matcher, str):
                if matcher == attribute:
                    return True
            else:
                if matcher(owner, attribute, value):
                    return True

        return False

    def match_attributes(self, owner : Entity, journal : EntityJournal) -> frozenset[str] | None:
        assert journal is not None

        if self.attribute_matchers is None:
            return None

        from ...collections.journalled.collection import JournalledCollection
        matched_attributes : Set[str] = set()

        diff = journal.get_diff()
        for attribute, value in diff.items():
            if isinstance(value, JournalledCollection) and not value.edited:
                continue

            if self.match_attribute(owner, attribute, value):
                matched_attributes.add(attribute)
        return frozenset(matched_attributes) if matched_attributes else None

    def call(self, owner : Entity, event : EntityDependencyEventType, entity : Entity, *, matched_attributes : frozenset[str] | None = None) -> None:
        self.log.debug(f"Calling {event.value} handler on {entity} with matched attributes {matched_attributes}")
        return self.handler(owner, event, entity, matched_attributes=matched_attributes)


    # MARK: Call
    def __call__(self, owner : Entity, event : EntityDependencyEventType, entity : Entity, journal : EntityJournal) -> bool:
        if owner is entity:
            raise ValueError("An entity cannot handle its own dependency events.")

        if not self.match_event(event):
            return False

        if not self.match_entity(owner, event, entity):
            return False

        matched_attributes : frozenset[str] | None = None
        if event.updated and self.attribute_matchers:
            assert journal is not None
            matched_attributes = self.match_attributes(owner, journal)
            if matched_attributes is None:
                return False

        self.call(owner, event, entity, matched_attributes=matched_attributes)
        return True