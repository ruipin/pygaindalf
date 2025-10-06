# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, Any, ClassVar, override

from pydantic import ConfigDict, Field, InstanceOf, field_validator
from requests import Session

from ....util.models import LoggableHierarchicalRootModel
from ...journal.session_manager import SessionManager
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
    root: InstanceOf[Entity] | None = Field(default=None, validate_default=False, description="The UID of the root entity.")

    @override
    def __hash__(self) -> int:
        return hash((type(self).__name__, hash(self.root)))

    @field_validator("root", mode="before")
    @classmethod
    def _validate_root(cls, root: Any) -> Entity | None:
        if not isinstance(root, Entity):
            msg = f"Expected Entity, got {type(root).__name__}"
            raise TypeError(msg)

        cls._do_validate_root(root)

        return root

    @classmethod
    def _do_validate_root(cls, root: Entity) -> None:
        pass

    if not TYPE_CHECKING:

        @override
        def __setattr__(self, name: str, value: Any) -> None:
            if name == "root" and (root := self.root) is not None:
                if value != root:
                    msg = "Cannot change root once set."
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
        root = self.root
        if root is not None and root.marked_for_deletion:
            msg = f"Root entity {root.uid} cannot be marked for deletion."
            raise RuntimeError(msg)

    def on_session_apply(self, session: Session) -> None:
        pass

    def on_session_commit(self, session: Session) -> None:  # noqa: ARG002
        unreachable_uids = self.entity_store.get_entity_uids() if self.root is None else self.entity_store.get_unreachable_uids(self.root.uid)
        if unreachable_uids:
            msg = f"Unreachable entities detected in entity store: {unreachable_uids}. This indicates a bug and/or memory leak in the session commit logic."
            raise RuntimeError(msg)

    def on_session_abort(self, session: Session) -> None:
        pass

    # MARK: EntityRecord Store
    entity_store: InstanceOf[EntityStore] = Field(default_factory=EntityStore, description="The entity store associated with this manager's portfolio.")
