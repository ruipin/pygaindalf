# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from collections.abc import Callable
from typing import TYPE_CHECKING, Any, dataclass_transform

from pydantic import Field, InstanceOf

from .....util.helpers import generics
from .....util.mixins import LoggableMixin


if TYPE_CHECKING:
    from ....journal import Journal
    from ..entity_record import EntityRecord
    from .protocols import EntityDependencyEventAttributeMatcher, EntityDependencyEventEntityMatcher, EntityDependencyEventHandler
    from .type_enum import EntityDependencyEventType


# MARK: Dataclass Transform base class
@dataclass_transform(kw_only_default=True, field_specifiers=(Field,))
class EntityDependencyEventHandlerDataclassTransform:
    pass


# MARK: Handler Base
class EntityDependencyEventHandlerBase[
    T_Owner: EntityRecord,
    T_Record: EntityRecord,
](
    LoggableMixin,
):
    if TYPE_CHECKING:
        handler: InstanceOf[EntityDependencyEventHandler[T_Owner, T_Record]]
        on_updated: bool
        on_deleted: bool
        entity_matchers: (
            tuple[InstanceOf[EntityDependencyEventEntityMatcher[T_Owner, T_Record]], ...]
            | InstanceOf[EntityDependencyEventEntityMatcher[T_Owner, T_Record]]
            | None
        ) = None
        attribute_matchers: (
            tuple[InstanceOf[EntityDependencyEventAttributeMatcher[T_Owner, T_Record]] | str, ...]
            | InstanceOf[EntityDependencyEventAttributeMatcher[T_Owner, T_Record]]
            | str
            | None
        ) = None

    get_owner_class = generics.GenericIntrospectionMethod[T_Owner]()
    get_record_class = generics.GenericIntrospectionMethod[T_Record]()

    def register(self, owner: type[T_Owner]) -> None:
        owner.register_dependency_event_handler(self)

    # MARK: Matching
    def match_event(self, event: EntityDependencyEventType) -> bool:
        if event.updated and self.on_updated:
            return True
        if event.deleted and self.on_deleted:  # noqa: SIM103 for visual alignment
            return True
        return False

    def match_entity(self, owner: T_Owner, event: EntityDependencyEventType, record: T_Record) -> bool:  # noqa: ARG002 this is for overidding
        if self.entity_matchers is None:
            return True

        if isinstance(self.entity_matchers, Callable):
            return self.entity_matchers(owner, record)

        return any(matcher(owner, record) for matcher in self.entity_matchers)

    def match_attribute(self, owner: T_Owner, record: T_Record, attribute: str, value: Any) -> bool:
        if self.attribute_matchers is None:
            return True

        if isinstance(self.attribute_matchers, Callable):
            return self.attribute_matchers(owner, record, attribute, value)
        if isinstance(self.attribute_matchers, str):
            return self.attribute_matchers == attribute

        for matcher in self.attribute_matchers:
            if isinstance(matcher, str):
                if matcher == attribute:
                    return True
            else:
                if matcher(owner, record, attribute, value):
                    return True

        return False

    def match_attributes(self, owner: T_Owner, record: T_Record, journal: Journal) -> frozenset[str] | None:
        assert journal is not None, "Journal must be provided when matching attributes."

        if self.attribute_matchers is None:
            return None

        from ....collections.journalled.collection import JournalledCollection

        matched_attributes: set[str] = set()

        diff = journal.get_diff()
        for attribute, value in diff.items():
            if isinstance(value, JournalledCollection) and not value.edited:
                continue

            if self.match_attribute(owner, record, attribute, value):
                matched_attributes.add(attribute)
        return frozenset(matched_attributes) if matched_attributes else None

    def call(self, owner: T_Owner, event: EntityDependencyEventType, record: T_Record, *, matched_attributes: frozenset[str] | None = None) -> None:
        self.log.debug(t"Calling {event.value} handler on {record} with matched attributes {matched_attributes}")
        self.handler(owner, event, record, matched_attributes=matched_attributes)

    # MARK: Call
    def __call__(self, owner: EntityRecord, event: EntityDependencyEventType, record: EntityRecord, journal: Journal) -> bool:
        owner_class = self.get_owner_class(owner=True)
        if not isinstance(owner, owner_class):
            return False

        record_class = self.get_record_class()
        if not isinstance(record, record_class):
            return False

        if owner is record:
            msg = "An entity cannot handle its own dependency events."
            raise ValueError(msg)

        if not self.match_event(event):
            return False

        if not self.match_entity(owner, event, record):
            return False

        matched_attributes: frozenset[str] | None = None
        if event.updated and self.attribute_matchers:
            assert journal is not None, "Journal must be provided when matching attributes."
            matched_attributes = self.match_attributes(owner, record, journal)
            if matched_attributes is None:
                return False

        self.call(owner, event, record, matched_attributes=matched_attributes)
        return True
