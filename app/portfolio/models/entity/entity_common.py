# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


import itertools

from abc import ABCMeta
from collections.abc import Callable, Generator, Iterable, Mapping
from collections.abc import Set as AbstractSet
from functools import cached_property
from string.templatelib import Template
from typing import TYPE_CHECKING, Any, NotRequired, Self, TypedDict, Unpack

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from ....util.helpers import generics, script_info
from ....util.helpers.classinstancemethod import classinstancemethod
from ....util.helpers.tstring import tstring_as_fstring
from ....util.models.annotated import is_non_child_type
from ....util.models.uid import Uid, UidProtocol


if TYPE_CHECKING:
    from ....util.helpers.classinstanceproperty import classinstanceproperty
    from ....util.logging import Logger
    from ...journal import Journal, Session, SessionManager
    from .entity import Entity


def _false(instance: type[EntityCommon] | EntityCommon, msg: Template | str, *, fail: bool = True) -> bool:
    if fail:
        if isinstance(msg, Template):
            msg = tstring_as_fstring(msg)
        __tracebackhide__ = True
        raise RuntimeError(msg)
    else:
        instance.log.warning(msg, stacklevel=4)
        return False


class EntityCommon[
    T_Journal: Journal,
](
    metaclass=ABCMeta,
):
    # MARK: Type Hints
    if TYPE_CHECKING:
        uid: Uid

        @classinstanceproperty
        def log(self) -> Logger: ...

    # MARK: Utilities
    @classmethod
    def get_record_model_fields(cls) -> Mapping[str, FieldInfo]:
        from .entity import Entity

        if issubclass(cls, Entity):
            return cls.get_record_type().model_fields
        else:
            assert issubclass(cls, BaseModel), f"Expected cls to be BaseModel, got {type(cls).__name__}."
            return cls.model_fields

    # MARK: Session
    @property
    def session_manager_or_none(self) -> SessionManager | None:
        from ...journal import SessionManager

        return SessionManager.get_global_manager_or_none()

    @property
    def session_manager(self) -> SessionManager:
        from ...journal import SessionManager

        return SessionManager.get_global_manager()

    @property
    def session_or_none(self) -> Session | None:
        if (manager := self.session_manager_or_none) is None:
            return None
        return manager.session

    @property
    def session(self) -> Session:
        if (session := self.session_or_none) is None:
            msg = "No active session found in the session manager."
            raise RuntimeError(msg)
        return session

    @property
    def in_session(self) -> bool:
        manager = self.session_manager_or_none
        return False if manager is None else manager.in_session

    # MARK: Journal
    get_journal_class = generics.GenericIntrospectionMethod[T_Journal]()

    def get_journal(self, *, create: bool = True, fail: bool = True) -> T_Journal | None:
        session = self.session if fail else self.session_or_none
        journal = session.get_journal(self.uid, create=create) if session is not None else None

        if fail and journal is None:
            msg = f"No journal found for entity {self}."
            raise RuntimeError(msg)
        if journal is not None:
            assert type(journal) is self.get_journal_class(), f"Expected journal of type {self.get_journal_class()}, got {type(journal)}."
        return journal

    @property
    def journal_or_none(self) -> T_Journal | None:
        if (journal := self.get_journal(create=False, fail=False)) is None or journal.superseded:
            return None
        return journal

    @property
    def journal(self) -> T_Journal:
        result = self.get_journal(create=True)
        if result is None:
            msg = f"No journal found for entity {self}."
            raise RuntimeError(msg)
        return result

    @property
    def j(self) -> T_Journal:
        return self.journal

    @property
    def has_journal(self) -> bool:
        return self.journal_or_none is not None

    @property
    def journal_or_self(self) -> T_Journal | Self:
        journal = self.journal_or_none
        return journal if journal is not None else self

    def get_journal_or_entity_field(self, field: str, *, edited_only: bool = False) -> Any:
        journal = self.journal_or_none
        if journal is not None and (not edited_only or journal.is_field_edited(field)):
            return getattr(journal, field)
        else:
            return getattr(self, field)

    @property
    def dirty(self) -> bool:
        if not self.in_session:
            return False
        j = self.journal_or_none
        return j.dirty if j is not None else False

    @property
    def has_diff(self) -> bool:
        if not self.in_session:
            return False
        j = self.journal_or_none
        return j.has_diff if j is not None else False

    def is_journal_field_edited(self, field: str) -> bool:
        journal = self.journal_or_none
        return journal.is_field_edited(field) if journal is not None else False

    def get_journal_field(self, field: str, *, create: bool = False) -> Any:
        journal = self.get_journal(create=create, fail=False)
        if journal is None or not journal.is_field_edited(field):
            return getattr(self, field)
        else:
            return getattr(journal, field)

    # MARK: Updates
    class UpdateAllowedOptions(TypedDict):
        allow_frozen_journal: NotRequired[bool]
        in_commit_only: NotRequired[bool]
        force_session: NotRequired[bool]
        allow_in_abort: NotRequired[bool]

    @classinstancemethod
    def _check_update_allowed(
        self,
        *,
        fail: bool = True,
        **options: Unpack[UpdateAllowedOptions],
    ) -> bool:
        from ...journal.session_manager import SessionManager

        if isinstance(self, EntityCommon):
            allow_frozen_journal: bool = options.get("allow_frozen_journal", False)

            if (journal := self.journal_or_none) is not None:
                if journal.superseded:
                    return _false(self, t"Journal for {self} is superseded; updates are not allowed.", fail=fail)
                if not allow_frozen_journal and journal.frozen:
                    return _false(self, t"Journal for {self} is frozen; updates are not allowed.", fail=fail)

        in_commit_only: bool = options.get("in_commit_only", True)
        force_session: bool = options.get("force_session", True)
        allow_in_abort: bool = options.get("allow_in_abort", False)

        session_manager = SessionManager.get_global_manager_or_none()
        if session_manager is None:
            if force_session or not script_info.is_unit_test():
                return _false(self, t"No active session manager; updates to {self} are not allowed.", fail=fail)
        else:
            if not session_manager.in_session or (session := session_manager.session) is None:
                return _false(self, t"No active session; updates to {self} are not allowed.", fail=fail)
            if allow_in_abort and session.in_abort:
                return _false(self, t"Updates to {self} are not allowed during session abort; currently in abort.", fail=fail)
            if in_commit_only and not session.in_commit:
                return _false(self, t"Updates to {self} are only allowed during session commit; currently not in commit.", fail=fail)

        return True

    @classinstancemethod
    def is_update_allowed(
        self,
        **options: Unpack[UpdateAllowedOptions],
    ) -> bool:
        __tracebackhide__ = True
        return self._check_update_allowed(fail=False, **options)

    @classinstancemethod
    def assert_update_allowed(
        self,
        **options: Unpack[UpdateAllowedOptions],
    ) -> None:
        __tracebackhide__ = True
        self._check_update_allowed(fail=True, **options)

    # MARK: Children
    # These are all entities that are considered reachable (and therefore not garbage collected) by the existence of this entity record.
    # I.e. those referenced by fields in the entity record as well as annotations.
    def _iter_obj_uids_field_ignore(self, field_name: str) -> bool:
        return field_name.startswith("_") or field_name in ("uid", "extra_dependency_uids", "entity_log")

    def _is_fieldinfo_a_potential_child(self, obj: BaseModel, field: str, *, info: FieldInfo | None = None) -> bool:
        if info is None:
            info = type(obj).model_fields.get(field, None)
        if info is None:
            msg = f"Field '{field}' not found in model fields of {type(obj).__name__}."
            raise RuntimeError(msg)

        extra = info.json_schema_extra if isinstance(info.json_schema_extra, dict) else None
        if extra is not None:
            if (is_child := extra.get("child", None)) is not None:
                assert isinstance(is_child, bool), f"Expected 'child' metadata of {obj} field {field} to be bool, got {type(is_child).__name__}."
                return is_child

        return not ((ann := info.annotation) is not None and is_non_child_type(ann))

    def _iter_obj_uids(self, obj: Any, *, children: bool, non_children: bool, use_journal: bool, recursive: bool) -> Generator[Uid]:  # noqa: C901
        if obj is None:
            return

        if obj is not self:
            if isinstance(obj, Uid):
                yield obj
                return

            elif isinstance(obj, UidProtocol):
                yield obj.uid
                return

        if not recursive:
            return

        if isinstance(obj, BaseModel):
            from ...journal import Journal

            journal = getattr(obj, "journal_or_none", None) if use_journal else None
            assert journal is None or isinstance(journal, Journal), f"Expected journal to be Journal or None, got {type(journal).__name__}."

            model_fields = type(obj).model_fields if not isinstance(obj, EntityCommon) else obj.get_record_model_fields()
            for field, info in model_fields.items():
                # Ignore fields
                if self._iter_obj_uids_field_ignore(field):
                    continue

                # Filter based on child / non-child
                is_child = self._is_fieldinfo_a_potential_child(obj, field, info=info)
                if (not children and is_child) or (not non_children and not is_child):
                    continue

                # Recurse
                value = getattr(journal if journal is not None and journal.is_field_edited(field) else obj, field, None)

                if value is None or value is self:
                    continue
                yield from self._iter_obj_uids(value, children=children, non_children=non_children, use_journal=use_journal, recursive=recursive)

        elif isinstance(obj, Mapping):
            for item in itertools.chain(obj.keys(), obj.values()):
                if item is self:
                    continue
                yield from self._iter_obj_uids(item, children=children, non_children=non_children, use_journal=use_journal, recursive=recursive)

        elif isinstance(obj, Iterable) and not isinstance(obj, (str, bytes, bytearray)):
            for item in obj:
                if item is self:
                    continue
                yield from self._iter_obj_uids(item, children=children, non_children=non_children, use_journal=use_journal, recursive=recursive)

    def iter_field_uids(self, *, use_journal: bool = False, children: bool = True, non_children: bool = True, recursive: bool = True) -> Iterable[Uid]:
        return self._iter_obj_uids(self, use_journal=use_journal, children=children, non_children=non_children, recursive=recursive)

    def iter_children_uids(self, *, use_journal: bool = False) -> Iterable[Uid]:
        yield from self.iter_field_uids(use_journal=use_journal, children=True, non_children=False)

    def iter_non_children_uids(self, *, use_journal: bool = False) -> Iterable[Uid]:
        yield from self.iter_field_uids(use_journal=use_journal, children=False, non_children=True)

    @cached_property
    def children_uids(self) -> AbstractSet[Uid]:
        from .entity import Entity

        if isinstance(self, Entity) and (record := self.record_or_none) is not None:
            return record.children_uids
        else:
            return frozenset(self.iter_children_uids())

    @cached_property
    def non_children_uids(self) -> AbstractSet[Uid]:
        from .entity import Entity

        if isinstance(self, Entity) and (record := self.record_or_none) is not None:
            return record.non_children_uids
        else:
            return frozenset(self.iter_non_children_uids())

    def _reset_uid_caches(self) -> None:
        self.__dict__.pop("children_uids", None)
        self.__dict__.pop("non_children_uids", None)

    @property
    def children(self) -> Iterable[Entity]:
        from .entity import Entity

        for uid in self.children_uids:
            yield Entity.by_uid(uid)

    @property
    def journal_children_uids(self) -> Iterable[Uid]:
        journal = self.journal_or_none
        uids = self.children_uids if journal is None else self.iter_children_uids(use_journal=True)
        yield from uids

    def get_children_uids(self, *, use_journal: bool = False) -> Iterable[Uid]:
        return self.journal_children_uids if use_journal else self.children_uids

    @property
    def journal_non_children_uids(self) -> Iterable[Uid]:
        journal = self.journal_or_none
        uids = self.non_children_uids if journal is None else self.iter_non_children_uids(use_journal=True)
        yield from uids

    def get_non_children_uids(self, *, use_journal: bool = False) -> Iterable[Uid]:
        return self.journal_non_children_uids if use_journal else self.non_children_uids

    def iter_hierarchy(
        self, *, condition: Callable[[Entity], bool] | None = None, use_journal: bool = False, check_condition_on_return: bool = True
    ) -> Iterable[Entity]:
        """Return a flat ordered set of all entities in this hierarchy."""
        from .entity import Entity
        from .entity_record import EntityRecord

        assert isinstance(self, (Entity, EntityRecord)), f"Expected self to be Entity or EntityRecord, got {type(self).__name__}."
        _self = self if isinstance(self, Entity) else self.entity

        if condition is not None and not condition(_self):
            return

        # Iterate dirty children journals
        for uid in self.get_children_uids(use_journal=use_journal):
            child = Entity.by_uid_or_none(uid)
            if child is None:
                msg = f"Child entity with UID {uid} not found in hierarchy traversal starting at {self}."
                raise RuntimeError(msg)

            if condition is not None and not condition(child):
                continue

            yield from child.iter_hierarchy(condition=condition, use_journal=use_journal, check_condition_on_return=check_condition_on_return)

        if check_condition_on_return and condition is not None and not condition(_self):
            msg = f"Entity record {self} failed condition check on return of yield_hierarchy."
            raise RuntimeError(msg)

        # Yield self, then return
        yield _self
