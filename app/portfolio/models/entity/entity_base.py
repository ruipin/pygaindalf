# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools
import inspect
import weakref

from abc import ABCMeta, abstractmethod
from collections.abc import Iterable, Mapping, MutableMapping
from typing import TYPE_CHECKING, Any, ClassVar, Self, final, override
from typing import cast as typing_cast

from pydantic import ConfigDict, Field, PrivateAttr, ValidationInfo, field_validator, model_validator

from ....util.callguard import CallguardClassOptions
from ....util.helpers import generics, type_hints
from ....util.mixins import HierarchicalMixinMinimal, NamedMixinMinimal
from ....util.models import LoggableHierarchicalModel
from ...util.uid import Uid, UidProtocol
from .entity_dependents import EntityDependents
from .entity_log import EntityLog
from .entity_record import EntityRecord


if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison

    from ...journal.session import Session
    from ...journal.session_manager import SessionManager
    from ..store import EntityStore


class EntityBase[
    T_Record: EntityRecord,
](
    type_hints.CachedTypeHintsMixin,
    LoggableHierarchicalModel,
    NamedMixinMinimal,
    metaclass=ABCMeta,
):
    __callguard_class_options__ = CallguardClassOptions["EntityBase"](
        ignore_patterns=(
            "_should_redirect_attribute_to_record",
            "_is_entity_attribute",
        ),
    )

    model_config = ConfigDict(
        extra="allow",
        frozen=True,
        validate_assignment=True,
    )

    # MARK: Construction
    @classmethod
    def _get_entity_store(cls) -> EntityStore:
        from ..store import EntityStore

        if (store := EntityStore.get_global_store()) is None:
            msg = f"Could not get entity store for {cls.__name__}. The global EntityStore is not set."
            raise ValueError(msg)

        return store

    def __new__(cls, uid: Uid | None = None, **data) -> Self:
        # Sanity check kwargs
        if "version" in data:
            msg = f"Cannot specify 'version' when creating a new {cls.__name__} instance."
            raise TypeError(msg)

        if "instance_name" in data:
            msg = f"Cannot specify 'instance_name' when creating a new {cls.__name__} instance."
            raise TypeError(msg)

        if "entity_log" in data:
            msg = f"Cannot specify 'entity_log' when creating a new {cls.__name__} instance."
            raise TypeError(msg)

        if "entity_dependents" in data:
            msg = f"Cannot specify 'entity_dependents' when creating a new {cls.__name__} instance."
            raise TypeError(msg)

        # Allow initializing from UID
        if uid is not None:
            if not isinstance(uid, Uid):
                msg = f"Expected 'uid' to be of type Uid, got {type(uid).__name__}."
                raise TypeError(msg)
            if data:
                msg = f"Cannot specify both 'uid' and other keyword arguments to {cls.__name__}."
                raise TypeError(msg)

            if (entity := cls.by_uid_or_none(uid)) is not None:
                entity._on_reinit(**data)  # noqa: SLF001
                return typing_cast("Self", entity)
            else:
                msg = f"Could not find existing {cls.__name__} with UID {uid}."
                raise ValueError(msg)

        # Prepare data for initialization
        data = cls._prepare_data_for_init(data)
        uid = data.get("uid", None)
        assert uid is not None, "Expected 'uid' to be set in data after preparation."
        if (entity := cls.by_uid_or_none(uid)) is not None:
            # Re-initialize existing instance
            if entity.exists:
                msg = f"Entity with UID {uid} already exists. Each entity must have a unique UID."
                raise ValueError(msg)

            new_inst_name = data.get("instance_name", None)
            assert entity.instance_name == new_inst_name, (
                f"Existing entity instance name '{entity.instance_name}' does not match new instance name '{new_inst_name}'."
            )

            entity._on_reinit(**data)  # noqa: SLF001
            return entity
        else:
            # Create new instance
            entity = super().__new__(cls)
            entity.__init__(**data)
            return entity

    def __init__(self, **data) -> None:
        # Creating a new entity
        if not self.initialized:
            super().__init__(**data)
            self.log.debug(t"Created new {type(self).__name__} with UID {self.uid} and instance name '{self.instance_name}'.")

    def _on_reinit(self, **data) -> None:
        if not self.exists:
            record_data = data.copy()

            for k in ("instance_name", "uid"):
                if (v := record_data.get(k, None)) is not None:
                    if v != getattr(self, k):
                        msg = f"Cannot change {k} of existing entity from '{getattr(self, k)}' to '{v}'."
                        raise ValueError(msg)
                    record_data.pop(k)

            self.update(**record_data)
            self.log.debug(t"Re-initialized {type(self).__name__} with UID {self.uid} and instance name '{self.instance_name}'.")

    @classmethod
    def _prepare_data_for_init(cls, data: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        # Validate inputs
        if data.get("instance_name", None) is not None:
            msg = f"Cannot specify 'instance_name' when creating a new {cls.__name__} instance."
            raise TypeError(msg)

        if data.get("uid", None) is not None:
            msg = f"Cannot specify 'uid' when creating a new {cls.__name__} instance."
            raise TypeError(msg)

        # Calculate instance name and UID
        data = cls._calculate_instance_name_and_uid(data)

        # Validate instance name
        if (instance_name := data.get("instance_name", None)) is None:
            msg = f"{cls.__name__}._calculate_instance_name_and_uid did not set 'instance_name'."
            raise ValueError(msg)
        if not isinstance(instance_name, str):
            msg = f"Expected {cls.__name__}._calculate_instance_name_and_uid to set 'instance_name' to be of type str, got {type(instance_name).__name__}."
            raise TypeError(msg)

        # Validate UID
        if (uid := data.get("uid", None)) is None:
            msg = f"{cls.__name__}._calculate_instance_name_and_uid did not set 'uid'."
            raise ValueError(msg)
        if not isinstance(uid, Uid):
            msg = f"Expected {cls.__name__}._calculate_instance_name_and_uid to set 'uid' to be of type Uid, got {type(uid).__name__}."
            raise TypeError(msg)

        uid_namespace = cls.uid_namespace()
        if uid.namespace != uid_namespace:
            msg = f"Uid namespace '{uid.namespace}' does not match expected namespace '{uid_namespace}'."
            raise ValueError(msg)

        data["uid"] = uid

        # Done
        return data

    # NOTE: We swallow the init argument to avoid pyright issues with multiple inheritance and __init__ signatures.
    def __init_subclass__(cls, *, init: bool = False, unsafe_hash: bool = True) -> None:
        super().__init_subclass__()

        if init:
            msg = "The 'init' argument must always be 'False' for EntityBase subclasses."
            raise ValueError(msg)
        if not unsafe_hash:
            msg = "The 'unsafe_hash' argument must always be 'True' for EntityBase subclasses."
            raise ValueError(msg)

        # Seed the dunder methods from the record type.
        record_type = cls.get_record_type(origin=True)
        for name, _ in inspect.getmembers_static(record_type, predicate=inspect.isfunction):
            if cls._should_copy_record_method_to_class(name):
                setattr(cls, name, functools.partialmethod(cls.call_record_method, name))

    # MARK: Lookup
    @classmethod
    def by_uid_or_none(cls, uid: Uid) -> Self | None:
        store = cls._get_entity_store()
        return typing_cast("Self | None", store.get(uid, None))

    @classmethod
    def by_uid(cls, uid: Uid) -> Self:
        if (entity := cls.by_uid_or_none(uid)) is None:
            msg = f"Could not find entity of type {cls.__name__} with UID {uid}."
            raise ValueError(msg)
        return entity

    @classmethod
    def by_record(cls, record: EntityRecord) -> Self:
        uid = record.uid
        if (entity := cls.by_uid_or_none(uid)) is not None:
            return entity
        return cls(uid=uid)

    @classmethod
    def narrow_to_uid(cls, value: Self | T_Record | Uid) -> Uid:
        if isinstance(value, Uid):
            if inspect.isabstract(cls):
                # try to convert to concrete entity so we can test isinstance
                entity = cls.by_uid_or_none(value)
                if entity is None:
                    # We cannot sanity check in this case - we want to support narrowing UIDs that may not yet exist in the store
                    pass
                elif not isinstance(entity, cls):
                    msg = f"UID {value} does not correspond to an instance of abstract class {cls.__name__}. Found instance of {type(entity).__name__}."
                    raise TypeError(msg)
            elif value.namespace != (cls_ns := cls.uid_namespace()):
                msg = f"UID namespace '{value.namespace}' does not match expected namespace '{cls_ns}'."
                raise ValueError(msg)
            return value
        elif isinstance(value, (cls, cls.get_record_type(origin=True))):
            return value.uid
        else:
            msg = f"Value must be a {cls.__name__} or Uid, got {type(value)}"
            raise TypeError(msg)

    @classmethod
    def narrow_to_instance_or_none(cls, value: Self | T_Record | Uid) -> Self | None:
        if isinstance(value, cls):
            return value

        elif isinstance(value, Uid):
            entity = cls.by_uid(value)
            if entity is None:
                return None
            if not isinstance(entity, cls):
                msg = f"UID {value} does not correspond to an instance of {cls.__name__}. Found instance of {type(entity).__name__}."
                raise TypeError(msg)
            return entity

        record_type = cls.get_record_type(origin=True)
        if isinstance(value, record_type):
            return typing_cast("Self | None", value.entity_or_none)

        else:
            msg = f"Value must be a {cls.__name__}, {record_type.__name__} or Uid, got {type(value)}"
            raise TypeError(msg)

    @classmethod
    def narrow_to_instance(cls, value: Self | T_Record | Uid) -> Self:
        if (result := cls.narrow_to_instance_or_none(value)) is None:
            msg = f"Could not find an entity of type {cls.__name__} for value {value}."
            raise ValueError(msg)
        return result

    # MARK: Instance Name
    PROPAGATE_INSTANCE_NAME_FROM_PARENT: ClassVar[bool] = False

    instance_name: str = Field(
        json_schema_extra={"readOnly": True},
        repr=False,
        exclude=True,
        description="Human-readable name for the entity instance, derived from its attributes.",
    )

    @classmethod
    @abstractmethod
    def calculate_instance_name_from_dict(cls, data: Mapping[str, Any]) -> str:
        msg = f"{cls.__name__} must implement the 'calculate_instance_name_from_dict' method to generate a name for the instance."
        raise NotImplementedError(msg)

    @classmethod
    def calculate_instance_name_from_instance(cls, instance: EntityBase) -> str:
        if (name := instance.instance_name) is not None:
            return name
        msg = f"{cls.__name__} must have a valid instance name."
        raise ValueError(msg)

    @classmethod
    def calculate_instance_name_from_arbitrary_data(cls, data: Any) -> str:
        if isinstance(data, cls):
            return cls.calculate_instance_name_from_instance(data)
        if not isinstance(data, dict):
            msg = f"Expected 'data' to be a dict or {cls.__name__}, got {type(data).__name__}."
            raise TypeError(msg)
        return cls.calculate_instance_name_from_dict(data)

    @model_validator(mode="before")
    @classmethod
    def _validate_instance_name_before(cls, data: Any) -> Self:
        # Validate inputs
        if (instance_name := data.get("instance_name", None)) is None:
            msg = f"Cannot create {cls.__name__} without a 'instance_name'."
            raise ValueError(msg)

        if not isinstance(instance_name, str):
            msg = f"Expected 'instance_name' to be of type str, got {type(instance_name).__name__}."
            raise TypeError(msg)

        assert instance_name == (calc_inst_name := cls._calculate_instance_name(data)), (
            f"Instance name {instance_name} does not match calculated instance name {calc_inst_name}."
        )

        # Done
        return data

    # MARK: Uid
    uid: Uid = Field(
        json_schema_extra={"readOnly": True},
        description="Unique identifier for the entity.",
    )

    @classmethod
    def uid_namespace(cls) -> str:
        """Return the namespace for the UID.

        This can be overridden in subclasses to provide a custom namespace.
        """
        return cls.__name__

    @classmethod
    def _calculate_uid(cls, data: Mapping[str, Any]) -> Uid:
        instance_name = data.get("instance_name", None)
        if instance_name is None:
            msg = f"{cls.__name__} must have an instance name when calculating its UID."
            raise ValueError(msg)

        instance_name = instance_name.removeprefix(cls.uid_namespace())
        instance_name = instance_name.removeprefix("@")

        return Uid(namespace=cls.uid_namespace(), id=instance_name)

    @classmethod
    def _calculate_instance_name(cls, data: Mapping[str, Any]) -> str:
        instance_name = cls.calculate_instance_name_from_dict(data)
        if not isinstance(instance_name, str) or not instance_name:
            msg = f"{cls.__name__} must have a valid instance name."
            raise ValueError(msg)

        return instance_name

    @classmethod
    def _calculate_instance_name_and_uid(cls, data: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        data["instance_name"] = cls._calculate_instance_name(data)
        data["uid"] = cls._calculate_uid(data)
        return data

    @model_validator(mode="before")
    @classmethod
    def _validate_uid_before(cls, data: Any) -> Self:
        # Validate inputs
        if (uid := data.get("uid", None)) is None:
            msg = f"Cannot create {cls.__name__} without a 'uid'."
            raise ValueError(msg)

        if not isinstance(uid, Uid):
            msg = f"Expected 'uid' to be of type Uid, got {type(uid).__name__}."
            raise TypeError(msg)

        assert uid.namespace == (cls_ns := cls.uid_namespace()), f"Expected uid.namespace to be {cls_ns}, got {uid.namespace} instead."

        # Done
        return data

    @model_validator(mode="after")
    def _validate_uid_after(self) -> Self:
        from .entity import Entity

        assert isinstance(self, Entity), f"Expected self to be an instance of Entity, got {type(self).__name__} instead."

        # Get a reference to the UID storage
        entity_store = self._get_entity_store()

        # If the entity already exists, we fail unless we are cloning the entity and incrementing the version
        existing = entity_store.get(self.uid, None)
        if existing and existing is not self:
            msg = f"Duplicate UID detected: {self.uid}. Each entity must have a unique UID."
            raise ValueError(msg)

        # Store the entity in the UID storage
        entity_store[self.uid] = self
        assert entity_store[self.uid] is self, f"Failed to store entity {self} in the entity store."

        # Create entity record
        self._create_first_record()

        return self

    # MARK: Entity Log
    entity_log: EntityLog = Field(
        default_factory=lambda data: EntityLog(data["uid"]),
        validate_default=True,
        repr=False,
        exclude=True,
        json_schema_extra={"readOnly": True},
        description="The audit log for this entity, which tracks changes made to it over time.",
    )

    @field_validator("entity_log", mode="after")
    @classmethod
    def _validate_audit_log(cls, entity_log: EntityLog, info: ValidationInfo) -> EntityLog:
        if (uid := info.data.get("uid", None)) is None or not isinstance(uid, Uid):
            msg = f"Entity must have a valid 'uid' to validate the audit log. Found: {uid}."
            raise ValueError(msg)

        if entity_log.entity_uid != uid:
            msg = f"Audit log UID '{entity_log.entity_uid}' does not match entity UID '{uid}'."
            raise ValueError(msg)

        return entity_log

    # MARK: Entity Dependents
    entity_dependents: EntityDependents = Field(
        default_factory=lambda data: EntityDependents(data["uid"]),
        validate_default=True,
        repr=False,
        exclude=True,
        description="The dependents of this entity, which tracks other entities that depend on this entity.",
    )

    @field_validator("entity_dependents", mode="after")
    @classmethod
    def _validate_entity_dependents(cls, entity_dependents: EntityDependents, info: ValidationInfo) -> EntityDependents:
        if (uid := info.data.get("uid", None)) is None or not isinstance(uid, Uid):
            msg = f"Entity must have a valid 'uid' to validate the entity dependents. Found: {uid}."
            raise ValueError(msg)

        if entity_dependents.entity_uid != uid:
            msg = f"Entity dependents UID '{entity_dependents.entity_uid}' does not match entity UID '{uid}'."
            raise ValueError(msg)

        return entity_dependents

    # MARK: Record
    _record: T_Record | None = PrivateAttr(default=None)

    if TYPE_CHECKING:
        version: int
    else:

        @property
        def version(self) -> int:
            return self.entity_log.version

    @property
    def record_or_none(self) -> T_Record | None:
        return self._record

    @property
    def record(self) -> T_Record:
        if self._record is None:
            msg = f"Entity {self} does not currently have a record. It may have been deleted."
            raise ValueError(msg)
        return self._record

    get_record_type = generics.GenericIntrospectionMethod[T_Record]()

    def _create_first_record(self) -> T_Record:
        if (extra := self.__pydantic_extra__) is None:
            msg = "Expected '__pydantic_extra__' to be set for Entity."
            raise ValueError(msg)

        record = self._create_record(**extra)
        extra.clear()
        return record

    def _create_record(self, **data) -> T_Record:
        record_type = self.get_record_type()

        record = record_type(uid=self.uid, **data)  # pyright: ignore[reportCallIssue]
        self._set_record(record)
        assert record.instance_parent is self, f"Expected record parent to be {self}, got {record.instance_parent} instead."

        return record

    def _set_record(self, record: T_Record | None) -> None:
        # Deleted
        if record is None:
            if self._record is not None and not self._record.deleted:
                msg = "Cannot delete entity with record that is not marked as deleted."
                raise ValueError(msg)

        # Updated
        else:
            if record.uid != self.uid:
                msg = f"Cannot change entity UID from {self.uid} to {record.uid}."
                raise ValueError(msg)

        self._record = record

        # Force instance parent to None if the record was deleted
        if record is None:
            object.__setattr__(self, "instance_parent_weakref", None)

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
        try:
            manager = self.session_manager
        except (TypeError, AttributeError, KeyError):
            return False
        return manager.in_session

    # MARK: Update
    def update(self, **kwargs) -> Self:
        record = self.record_or_none

        if (new_parent := kwargs.pop("instance_parent", None)) is not None:
            if new_parent is None:
                msg = "Cannot set 'instance_parent' to None. To remove the parent, delete the entity instead."
                raise ValueError(msg)
            elif self.exists:
                if new_parent is not self.instance_parent:
                    msg = "Cannot change the 'instance_parent' of an existing entity. The parent is managed by the associated Entity instance and should not be changed directly."
                    raise ValueError(msg)
            else:
                object.__setattr__(
                    self, "instance_parent_weakref", weakref.ref(new_parent) if not isinstance(new_parent, weakref.ReferenceType) else new_parent
                )

        record = self._create_record(**kwargs) if record is None else record.update(**kwargs)
        assert self.record_or_none is record, f"Expected record to be {record}, got {self.record_or_none} instead."
        return self

    @property
    def superseded(self) -> bool:
        return self.deleted

    @property
    def superseding(self) -> Self | None:
        return self if not self.superseded else None

    def on_init_record(self, record: T_Record) -> None:
        self._set_record(record)

    # MARK: Deletion
    def delete(self) -> None:
        if self.deleted:
            msg = f"Cannot delete {type(self).__name__} with UID {self.uid} because it is already deleted."
            raise RuntimeError(msg)

        record = self.record_or_none
        if record is None:
            msg = f"Cannot delete {type(self).__name__} with UID {self.uid} because the corresponding record could not be found."
            raise RuntimeError(msg)

        record.delete()

        assert self.record.marked_for_deletion, f"Expected record to be marked for deletion, got {self.record.marked_for_deletion} instead."

    @property
    def exists(self) -> bool:
        result = self.record_or_none is not None
        assert self.entity_log.exists == result, f"Expected entity log existence to be {result}, got {self.entity_log.exists} instead."
        return result

    @property
    def deleted(self) -> bool:
        return not self.exists

    @property
    def marked_for_deletion(self) -> bool:
        record = self.record_or_none
        return record is None or record.marked_for_deletion

    def on_delete_record(self) -> None:
        self._set_record(None)

    # MARK: Revertion
    def revert(self) -> None:
        if (session := self.session_or_none) is None:
            msg = f"Cannot revert {type(self).__name__} with UID {self.uid} because it is not in an active session."
            raise RuntimeError(msg)

        if not session.in_abort and not session.in_commit:
            msg = f"Cannot revert {type(self).__name__} with UID {self.uid} because the session is not in the process of being committed or aborted."
            raise RuntimeError(msg)

        if self.is_reachable(recursive=True, use_journal=True):
            msg = f"Cannot revert {type(self).__name__} with UID {self.uid} because it is still reachable from its parent."
            raise RuntimeError(msg)

        record = self.record_or_none
        version = self.version

        self.entity_log.revert()
        if record is not None:
            record.revert()
            self._set_record(None)

        if version != self.version + 1:
            msg = f"Expected entity log version to be {version + 1} after revert, got {self.version} instead."
            raise RuntimeError(msg)

    # MARK: Fields
    @final
    @classmethod
    def _should_copy_record_method_to_class(cls, name: str) -> bool:
        if not name.startswith("__") or not name.endswith("__"):
            return False

        if name in ("__len__", "__iter__", "__getitem__", "__setitem__", "__contains__"):
            return True

        if cls._is_entity_attribute(name):
            return False

        if name.startswith("__pydantic"):
            return False

        return name not in (
            "__class__",
            "__del__",
            "__getattr__",
            "__class_vars__",
            "__private_attributes__",
            "__signature__",
        )

    @final
    @classmethod
    def _should_redirect_attribute_to_record(cls, attr: str) -> bool:
        if attr.startswith("_"):
            return False

        return not cls._is_entity_attribute(attr)

    @final
    @classmethod
    def _is_entity_attribute(cls, attr: str) -> bool:
        return hasattr(cls, attr) or type_hints.get_type_hint(cls, attr) is not None

    if not TYPE_CHECKING:

        @override
        def __getattribute__(self, name: str) -> Any:
            if name == "__class__" or not EntityBase._should_redirect_attribute_to_record(name):
                return super().__getattribute__(name)
            return self.record.__getattribute__(name)

        @override
        def __setattr__(self, name: str, value: object) -> None:
            if not self._should_redirect_attribute_to_record(name):
                return super().__setattr__(name, value)
            return self.record.__setattr__(name, value)

    @override
    def __dir__(self) -> Iterable[str]:
        record = self.record_or_none
        if record is None:
            return super().__dir__()

        values = set()
        for name in super().__dir__():
            values.add(name)
            yield name

        for name in dir(record):
            if name not in values:
                yield name

    def call_record_method(self, name: str, *args, **kwargs) -> Any:
        method = getattr(self.record, name)
        return method(*args, **kwargs)

    # MARK: Children
    @property
    def children(self) -> Iterable[EntityBase]:
        for uid in self.record.children_uids:
            yield EntityBase.by_uid(uid)

    def is_reachable(self, *, recursive: bool = True, use_journal: bool = False) -> bool:
        from ..root import EntityRoot

        parent = self.instance_parent
        if parent is None:
            return False
        if isinstance(parent, EntityRoot):
            return True
        if not isinstance(parent, EntityBase):
            msg = f"Entity {self} has a parent of type {type(parent).__name__}, expected Entity or EntityRoot."
            raise TypeError(msg)

        # Check if parent contains us
        record = parent.record_or_none
        if record is None:
            return False

        uids = record.get_children_uids(use_journal=use_journal)
        if self.uid not in uids:
            return False

        # Recurse up the tree
        if not recursive:
            return True
        else:
            return parent.is_reachable(use_journal=use_journal, recursive=True)

    # MARK: Utilities
    def sort_key(self) -> SupportsRichComparison:
        return self.record.sort_key()

    @override
    def __eq__(self, other: object) -> bool:
        return isinstance(other, UidProtocol) and self.uid == other.uid

    @override
    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    @override
    def __hash__(self) -> int:
        return hash(self.uid)

    def _customize_str_repr(self, spr: str) -> str:
        assert spr and spr[0] == "<", f"Expected string representation to start with '<', got {spr} instead."  # noqa: PT018

        result = spr.removesuffix(">")
        result += f" v{self.version}"
        if not self.exists:
            result += " (D)"

        result = result.replace(f"{type(self).__name__}@", "")
        return result + ">"

    @override
    def __str__(self) -> str:
        return self._customize_str_repr(super(HierarchicalMixinMinimal, self).__str__())

    @override
    def __repr__(self) -> str:
        return self._customize_str_repr(super(HierarchicalMixinMinimal, self).__repr__())
