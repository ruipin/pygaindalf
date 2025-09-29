# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, Any, ClassVar, override

from pydantic import ConfigDict, Field, InstanceOf, field_validator
from requests import Session

from ....util.models import LoggableHierarchicalRootModel
from ...journal.session_manager import SessionManager
from ...util import SupersededError
from ...util.uid import Uid
from ..entity import Entity
from ..store.entity_store import EntityStore


if TYPE_CHECKING:
    from ...journal.session import Session


class EntityRoot(LoggableHierarchicalRootModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        validate_assignment=True,
    )

    # MARK: Global instance behaviour
    _global_root: ClassVar[EntityRoot | None] = None

    @staticmethod
    def get_global_root_or_none() -> EntityRoot | None:
        return EntityRoot._global_root

    @staticmethod
    def get_global_root() -> EntityRoot:
        if (root := EntityRoot._global_root) is None:
            msg = "Global EntityRoot is not set. Please create an EntityRoot instance and call set_as_global_root() on it before accessing the global root."
            raise ValueError(msg)
        if EntityStore.get_global_store() is not root.entity_store:
            msg = "Global EntityStore instance does not match the one from the global EntityRoot."
            raise RuntimeError(msg)
        return root

    @classmethod
    def create_global_root[T: EntityRoot](cls: type[T]) -> T:
        root = cls()
        root.set_as_global_root()
        return root

    @classmethod
    def get_or_create_global_root[T: EntityRoot](cls: type[T]) -> T:
        if (root := EntityRoot._global_root) is None or not isinstance(root, cls):
            root = cls.create_global_root()
        return root

    def set_as_global_root(self) -> None:
        EntityRoot._global_root = self

    @staticmethod
    def clear_global_root() -> None:
        EntityRoot._global_root = None

    # MARK: Root entity
    root_uid: Uid | None = Field(default=None, validate_default=False, description="The UID of the root entity.")

    @property
    def root(self) -> Entity:
        if self.root_uid is None:
            msg = f"{type(self).__name__} has no root entity set."
            raise ValueError(msg)
        return self.entity_store[self.root_uid]

    @root.setter
    def root(self, value: Uid | Entity) -> None:
        uid = Entity.narrow_to_uid(value)
        if Entity.by_uid_or_none(uid) is None:
            msg = f"No Entity found with uid {value}"
            raise ValueError(msg)
        self.root_uid = uid

    @override
    def __hash__(self) -> int:
        return hash((type(self).__name__, hash(self.root_uid)))

    @field_validator("root_uid", mode="before")
    @classmethod
    def _validate_root_uid(cls, root_uid: Any) -> Uid | None:
        if not isinstance(root_uid, Uid):
            msg = f"Expected Uid, got {type(root_uid).__name__}"
            raise TypeError(msg)

        root = Entity.by_uid(root_uid)
        if root.superseded:
            msg = f"Entity '{root_uid}' is superseded."
            raise SupersededError(msg)

        cls._do_validate_root_uid(root_uid)

        return root_uid

    @classmethod
    def _do_validate_root_uid(cls, root_uid: Uid) -> None:
        pass

    if not TYPE_CHECKING:

        @override
        def __setattr__(self, name: str, value: Any) -> None:
            if name == "root_uid" and (root_uid := self.root_uid) is not None:
                if value != root_uid:
                    msg = "Cannot change root_uid once set."
                    raise AttributeError(msg)
                return None
            return super().__setattr__(name, value)

    # MARK: Session Manager
    session_manager: InstanceOf[SessionManager] = Field(default_factory=SessionManager, description="Session manager associated with this entity root")

    def on_session_start(self, session: Session) -> None:
        pass

    def on_session_end(self, session: Session) -> None:
        pass

    def on_session_notify(self, session: Session) -> None:  # noqa: ARG002
        superseding = self.root.superseding_or_none
        if superseding is None:
            msg = "Cannot refresh entities: entity root has no superseding root."
            raise ValueError(msg)

        if superseding is not self.root:
            self.root = superseding

        self.garbage_collect(use_journal=True)

    def on_session_apply(self, session: Session) -> None:
        pass

    def on_session_commit(self, session: Session) -> None:
        pass

    def on_session_abort(self, session: Session) -> None:
        pass

    # MARK: Entity Store
    entity_store: InstanceOf[EntityStore] = Field(default_factory=EntityStore, description="The entity store associated with this manager's portfolio.")

    def garbage_collect(self, *, use_journal: bool = False, who: str = "system", why: str = "garbage collect") -> None:
        if self.root_uid is None:
            self.entity_store.reset()
        else:
            with self.session_manager(reuse=use_journal, actor=who, reason=why):
                self.entity_store.mark_and_sweep(self.root_uid, use_journal=use_journal)
