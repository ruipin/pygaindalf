# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from pydantic import Field, field_validator, ConfigDict, InstanceOf, PrivateAttr, computed_field
from typing import Any, override, ClassVar, TYPE_CHECKING

from requests import Session

from ....util.callguard import callguard_property
from ....util.mixins import LoggableHierarchicalModel
from ....util.helpers import script_info

from ...journal.session_manager import SessionManager
from ...journal.session import JournalSession

from ..uid import Uid
from ..store.entity_store import EntityStore
from ..entity import Entity



class EntityRoot(LoggableHierarchicalModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=False,
        validate_assignment=True,
    )


    # MARK: Global instance behaviour
    _global_root : ClassVar[EntityRoot | None] = None

    @staticmethod
    def get_global_root_or_none() -> EntityRoot | None:
        return EntityRoot._global_root

    @staticmethod
    def get_global_root() -> EntityRoot:
        if (root := EntityRoot._global_root) is None:
            raise ValueError("Global EntityRoot is not set. Please create an EntityRoot instance and call set_as_global_root() on it before accessing the global root.")
        if EntityStore.get_global_store() is not root.entity_store:
            raise RuntimeError("Global EntityStore instance does not match the one from the global EntityRoot.")
        return root

    @classmethod
    def create_global_root[T : EntityRoot](cls : type[T]) -> T:
        root = cls()
        root.set_as_global_root()
        return root

    @classmethod
    def get_or_create_global_root[T : EntityRoot](cls : type[T]) -> T:
        if (root := EntityRoot._global_root) is None or not isinstance(root, cls):
            root = cls.create_global_root()
        return root

    def set_as_global_root(self) -> None:
        EntityRoot._global_root = self

    @staticmethod
    def clear_global_root() -> None:
        EntityRoot._global_root = None


    # MARK: Root entity
    root_uid : Uid | None = Field(default=None, validate_default=False, description="The UID of the root entity.")

    @property
    def root(self) -> Entity:
        if self.root_uid is None:
            raise ValueError(f"{self.__class__.__name__} has no root entity set.")
        return self.entity_store[self.root_uid]

    @root.setter
    def root(self, value : Uid | Entity) -> None:
        uid = Entity.narrow_to_uid(value)
        if Entity.by_uid(uid) is None:
            raise ValueError(f"No Entity found with uid {value}")
        self.root_uid = uid

    @override
    def __hash__(self) -> int:
        return hash((self.__class__.__name__, hash(self.root_uid)))

    @field_validator('root_uid', mode='before')
    @classmethod
    def _validate_root_uid(cls, root_uid : Any) -> Uid | None:
        if not isinstance(root_uid, Uid):
            raise TypeError(f"Expected Uid, got {type(root_uid).__name__}")

        root = Entity.by_uid(root_uid)
        if root is None:
            raise ValueError(f"No Entity found with uid {root_uid}")
        if root.superseded:
            raise ValueError(f"Entity '{root_uid}' is superseded.")

        cls._do_validate_root_uid(root_uid)

        return root_uid

    @classmethod
    def _do_validate_root_uid(cls, root_uid : Uid) -> None:
        pass

    if not TYPE_CHECKING:
        @override
        def __setattr__(self, name: str, value: Any) -> None:
            if name == 'root_uid' and (root_uid := self.root_uid) is not None:
                if value != root_uid:
                    raise AttributeError("Cannot change root_uid once set.")
                return
            return super().__setattr__(name, value)


    # MARK: Session Manager
    session_manager : InstanceOf[SessionManager] = Field(default_factory=SessionManager, description="Session manager associated with this entity root")

    def on_session_start(self, session : JournalSession) -> None:
        pass

    def on_session_end(self, session : JournalSession) -> None:
        pass

    def on_session_commit(self, session : JournalSession) -> None:
        superseding = self.root.superseding
        if superseding is None:
            raise ValueError("Cannot refresh entities: entity root has no superseding root.")

        if superseding is not self.root:
            self.root = superseding

        self.garbage_collect(who=session.actor, why=session.reason)

    def on_session_abort(self, session : JournalSession) -> None:
        pass


    # MARK: Entity Store
    entity_store : InstanceOf[EntityStore] = Field(default_factory=EntityStore, description="The entity store associated with this manager's portfolio.")

    def garbage_collect(self, who : str = 'system', why : str = 'garbage collect') -> None:
        if self.root_uid is None:
            self.entity_store.reset()
        else:
            self.entity_store.mark_and_sweep(self.root_uid, who=who, why=why)
