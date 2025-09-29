# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import annotationlib
import inspect
import sys
import weakref

from abc import ABCMeta, abstractmethod
from collections.abc import Callable, Iterable, MutableMapping, MutableSet
from functools import cached_property
from typing import TYPE_CHECKING, Any, ClassVar, Self, get_type_hints, override
from typing import cast as typing_cast

from frozendict import frozendict
from pydantic import ConfigDict, Field, PositiveInt, PrivateAttr, ValidationInfo, computed_field, field_validator, model_validator

from ....util.callguard import CallguardClassOptions
from ....util.helpers import cached_classproperty, generics, script_info, type_hints
from ....util.helpers.weakref import WeakRef
from ....util.mixins import NamedMixinMinimal, NamedProtocol
from ....util.models import LoggableHierarchicalModel


if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison

    from ...collections.uid_proxy import UidProxySet
    from ...journal.entity_journal import EntityJournal
    from ...journal.session import Session
    from ...journal.session_manager import SessionManager
    from ..annotation import Annotation
    from ..store.entity_store import EntityStore
    from .entity_proxy import EntityProxy

from ...util.superseded import superseded_check
from ...util.uid import Uid
from .dependency_event_handler import EntityDependencyEventHandlerRecord, EntityDependencyEventType
from .entity_audit_log import EntityAuditLog, EntityAuditType
from .entity_base import EntityBase
from .entity_dependents import EntityDependents
from .entity_fields import EntityFields


ENTITY_SUBCLASSES: MutableSet[type[Entity]] = set()
PROXY_TYPES: MutableMapping[type[Entity], type[EntityProxy]] = {}


class Entity[T_Journal: EntityJournal, T_Proxy: EntityProxy](LoggableHierarchicalModel, EntityBase, EntityFields, NamedMixinMinimal, metaclass=ABCMeta):
    __callguard_class_options__ = CallguardClassOptions["Entity"](
        decorator=superseded_check,
        decorate_public_methods=True,
        ignore_patterns=("superseding", "superseded", "deleted", "marked_for_deletion", "uid", "version"),
    )

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )

    # MARK: Metaclass infrastructure
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        ENTITY_SUBCLASSES.add(cls)

        # Collect field aliases into a single collection
        aliases: dict[str, str] = {}
        reverse: dict[str, str] = {}

        for name, info in cls.model_fields.items():
            if info.alias:
                aliases[info.alias] = name
                reverse[name] = info.alias

        cls.model_field_aliases = frozendict(aliases)
        cls.model_field_reverse_aliases = frozendict(reverse)

        # Initialise dependencies
        cls.__init_dependencies__()

    @cached_classproperty
    def __cached_type_hints__(cls) -> dict[str, Any]:
        return get_type_hints(cls)

    @classmethod
    def is_update_allowed(cls, *, in_commit_only: bool = True, allow_in_abort: bool = False, force_session: bool = False) -> bool:
        # Check if we are in the middle of a commit
        from ...journal.session_manager import SessionManager

        session_manager = SessionManager.get_global_manager_or_none()
        if session_manager is None:
            if force_session or not script_info.is_unit_test():
                return False
        else:
            if not session_manager.in_session or (session := session_manager.session) is None:
                return False
            if allow_in_abort and session.in_abort:
                return True
            if in_commit_only and not session.in_commit:
                return False

        return True

    # MARK: Initialization / Destruction
    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        if not cls.is_update_allowed(in_commit_only=False):
            msg = f"Not allowed to create {cls.__name__} instances outside of a session."
            raise RuntimeError(msg)
        return super().__new__(cls, *args, **kwargs)

    @override
    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)

        self.entity_log.on_init(self)
        self.entity_dependents.on_init(self)
        if self.entity_log.most_recent.what == EntityAuditType.CREATED and (session := self.session_or_none) is not None:
            session.on_entity_created(self)

    # MARK: Deletion
    @property
    def deleted(self) -> bool:
        if not self.superseded:
            return False

        superseding_log = self.entity_log.get_entry_by_version(self.version + 1)
        if superseding_log is None:
            msg = f"Entity {self} is marked as superseded but no audit log entry found for version {self.version + 1}."
            raise ValueError(msg)

        return superseding_log.what == EntityAuditType.DELETED

    @property
    def marked_for_deletion(self) -> bool:
        if self.deleted:
            return True

        journal = self.get_journal(create=False, fail=False)
        return journal.marked_for_deletion if journal is not None else False

    def __del__(self) -> None:
        # No need to track deletion in finalizing state
        if sys.is_finalizing:
            return

        self.log.debug(t"Entity __del__ called for {self}.")
        if not self.superseded:
            self.log.warning(
                t"Entity {self} is being garbage collected without being superseded. This may indicate a logic error or improper session management."
            )
            self._apply_deletion(who="system", why="__del__")

    def delete(self) -> None:
        if self.marked_for_deletion:
            return

        if not self.is_update_allowed(in_commit_only=False):
            msg = f"Not allowed to delete {type(self).__name__} instances outside of a session."
            raise RuntimeError(msg)

        self.log.debug(t"Entity delete called for {self}.")

        # Only situation is_update_allowed returns True but we are not in a session is during unit tests without a session manager,
        # in which case it is fine to immediately delete the entity
        if self.in_session:
            self.journal.delete()
        else:
            assert script_info.is_unit_test()
            self._apply_deletion()

    def propagate_deletion(self) -> None:
        if not self.marked_for_deletion:
            return

        for uid in self.children_uids:
            child = Entity.by_uid_or_none(uid)
            if child is not None and not child.marked_for_deletion:
                child.delete()

    def apply_deletion(self, *, who: str | None = None, why: str | None = None) -> None:
        if not self.is_update_allowed(allow_in_abort=True):
            msg = f"Not allowed to apply deletion to {type(self).__name__} instances outside of a session commit."
            raise RuntimeError(msg)

        self._apply_deletion(who=who, why=why)

    def _apply_deletion(self, *, who: str | None = None, why: str | None = None) -> None:
        self.entity_log.on_delete(self, who=who, why=why)
        self.entity_dependents.on_delete(self)

        entity_store = self._get_entity_store()
        del entity_store[self.uid]

        self.log.info(t"Entity {self} has been deleted.")

    # MARK: Instance Name
    PROPAGATE_INSTANCE_NAME_FROM_PARENT: ClassVar[bool] = False
    STRICT_INSTANCE_NAME_VALIDATION: ClassVar[bool] = True

    @classmethod
    @abstractmethod
    def calculate_instance_name_from_dict(cls, data: dict[str, Any]) -> str:
        msg = f"{cls.__name__} must implement the 'calculate_instance_name_from_dict' method to generate a name for the instance."
        raise NotImplementedError(msg)

    @classmethod
    def calculate_instance_name_from_instance(cls, instance: Entity) -> str:
        if not isinstance(instance, NamedProtocol):
            msg = f"Expected instance of {cls.__name__}, got {type(instance).__name__}."
            raise TypeError(msg)
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

    @model_validator(mode="after")
    def _validate_instance_name(self) -> Self:
        if type(self).STRICT_INSTANCE_NAME_VALIDATION:
            dict_name = type(self).calculate_instance_name_from_dict(self.__dict__)
            instance_name = type(self).calculate_instance_name_from_instance(self)
            if instance_name != dict_name:
                msg = f"Instance name '{instance_name}' does not match the calculated name from the dictionary '{dict_name}'."
                raise ValueError(msg)

        return self

    @computed_field(description="The instance name, or class name if not set.")
    @property
    @override
    def instance_name(self) -> str:
        """Get the instance name, or class name if not set."""
        return self.calculate_instance_name_from_dict(self.__dict__)

    # MARK: Uid
    # TODO: These should all be marked Final, but pydantic is broken here, see https://github.com/pydantic/pydantic/issues/10474#issuecomment-2478666651

    @classmethod
    def uid_namespace(cls) -> str:
        """Return the namespace for the UID.

        This can be overridden in subclasses to provide a custom namespace.
        """
        return cls.__name__

    @classmethod
    def _calculate_uid(cls, data: dict[str, Any]) -> Uid:
        instance_name = cls.calculate_instance_name_from_dict(data)
        if instance_name is None:
            msg = f"{cls.__name__} must have an instance name when calculating its UID."
            raise ValueError(msg)

        instance_name = instance_name.removeprefix(cls.uid_namespace())
        instance_name = instance_name.removeprefix("@")

        return Uid(namespace=cls.uid_namespace(), id=instance_name)

    @model_validator(mode="before")
    @classmethod
    def _validate_uid_before(cls, data: Any) -> Self:
        if (uid := data.get("uid", None)) is None:
            uid = {}

        if not isinstance(uid, Uid):
            uid = cls._calculate_uid(data)

        if not isinstance(uid, Uid):
            msg = f"Expected 'uid' to be of type Uid, got {type(uid).__name__}."
            raise TypeError(msg)

        uid_namespace = cls.uid_namespace()
        if uid.namespace != uid_namespace:
            msg = f"Uid namespace '{uid.namespace}' does not match expected namespace '{uid_namespace}'."
            raise ValueError(msg)

        # If this entity already exists in the store, confirm a version was explicitly passed
        if (existing := cls._get_entity_store().get(uid, None)) is not None:
            version = data.get("version", None)
            if version is None:
                msg = f"Entity with UID {uid} already exists. You must provide an explicit version to create a new version of the entity."
                raise ValueError(msg)
            elif version != existing.entity_log.next_version:
                msg = f"Entity with UID {uid} already exists with version {existing.version}. You must provide the next version {existing.entity_log.next_version} to create a new version of the entity."
                raise ValueError(msg)

        data["uid"] = uid
        return data

    @model_validator(mode="after")
    def _validate_uid_after(self) -> Self:
        # Get a reference to the UID storage
        entity_store = self._get_entity_store()

        # If the entity already exists, we fail unless we are cloning the entity and incrementing the version
        existing = entity_store.get(self.uid, None)
        if existing and existing is not self:
            if self.version <= existing.version:
                msg = f"Duplicate UID detected: {self.uid} with versions {self.version} vs {existing.version}. Each entity must have a unique UID or increment the version."
                raise ValueError(msg)

        # Store the entity in the UID storage
        entity_store[self.uid] = self

        return self

    @classmethod
    def _get_entity_store(cls) -> EntityStore:
        from ..store.entity_store import EntityStore

        if (uid_storage := EntityStore.get_global_store()) is None:
            msg = f"Global EntityStore is not set. Please create an EntityStore instance and call set_as_global_store() on it before creating {cls.__name__} instances."
            raise ValueError(msg)
        return uid_storage

    @classmethod
    def by_uid_or_none[T: Entity](cls: type[T], uid: Uid) -> T | None:
        if not isinstance(uid, Uid):
            msg = f"Expected 'uid' to be of type Uid, got {type(uid).__name__}."
            raise TypeError(msg)
        result = cls._get_entity_store().get(uid, None)
        if result is None:
            return None
        if not isinstance(result, cls):
            msg = f"UID storage returned an instance of {type(result).__name__} instead of {cls.__name__}."
            raise TypeError(msg)
        return result

    @classmethod
    def by_uid[T: Entity](cls: type[T], uid: Uid) -> T:
        if (result := cls.by_uid_or_none(uid)) is None:
            msg = f"Could not find an entity of type {cls.__name__} for UID {uid}."
            raise ValueError(msg)
        return result

    @classmethod
    def narrow_to_uid[T: Entity](cls: type[T], value: T | Uid) -> Uid:
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
            elif value.namespace == cls.uid_namespace():
                msg = f"UID namespace '{value.namespace}' does not match expected namespace '{cls.uid_namespace()}'."
                raise ValueError(msg)
            return value
        elif isinstance(value, cls):
            return value.uid
        else:
            msg = f"Value must be a {cls.__name__} or Uid, got {type(value)}"
            raise TypeError(msg)

    @classmethod
    def narrow_to_entity_or_none[T: Entity](cls: type[T], value: T | Uid) -> T | None:
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

        else:
            msg = f"Value must be a {cls.__name__} or Uid, got {type(value)}"
            raise TypeError(msg)

    @classmethod
    def narrow_to_entity[T: Entity](cls: type[T], value: T | Uid) -> T:
        if (result := cls.narrow_to_entity_or_none(value)) is None:
            msg = f"Could not find an entity of type {cls.__name__} for value {value}."
            raise ValueError(msg)
        return result

    # MARK: Parent
    @property
    def entity_parent_or_none(self) -> Entity | None:
        parent = self.instance_parent
        if parent is None or not isinstance(parent, Entity):
            return None
        if parent.superseded:
            return None  # TODO: Should this be 'parent.superseding_or_none' ?
        return parent

    @property
    def entity_parent(self) -> Entity:
        if (parent := self.entity_parent_or_none) is None:
            msg = f"{type(self).__name__} instance {self.uid} has no valid entity parent."
            raise ValueError(msg)
        return parent

    # MARK: Meta
    _initialized: bool = PrivateAttr(default=False)
    entity_log: EntityAuditLog = Field(
        default_factory=lambda data: EntityAuditLog(data["uid"]),
        validate_default=True,
        repr=False,
        exclude=True,
        json_schema_extra={"readOnly": True},
        description="The audit log for this entity, which tracks changes made to it over time.",
    )
    version: PositiveInt = Field(
        default_factory=lambda data: data["entity_log"].next_version,
        validate_default=True,
        ge=1,
        json_schema_extra={"readOnly": True},
        description="The version of this entity. Incremented when the entity is cloned as part of an update action.",
    )

    @field_validator("entity_log", mode="after")
    @classmethod
    def _validate_audit_log(cls, entity_log: EntityAuditLog, info: ValidationInfo) -> EntityAuditLog:
        if (uid := info.data.get("uid", None)) is None or not isinstance(uid, Uid):
            msg = f"Entity must have a valid 'uid' to validate the audit log. Found: {uid}."
            raise ValueError(msg)
        if entity_log.entity_uid != uid:
            msg = f"Audit log UID '{entity_log.entity_uid}' does not match entity UID '{uid}'."
            raise ValueError(msg)
        return entity_log

    @field_validator("version", mode="after")
    @classmethod
    def _validate_version(cls, version: PositiveInt, info: ValidationInfo) -> PositiveInt:
        if (entity_log := info.data.get("entity_log", None)) is None or not isinstance(entity_log, EntityAuditLog):
            msg = f"Entity must have a valid 'entity_log' to validate the version. Found: {entity_log}."
            raise ValueError(msg)
        if version != entity_log.next_version:
            msg = f"Entity version '{version}' does not match the next audit log version '{entity_log.version + 1}'. The version should be incremented when the entity is cloned as part of an update action."
            raise ValueError(msg)
        return version

    def is_newer_version_than(self, other: Entity) -> bool:
        if not isinstance(other, Entity):
            msg = f"Expected Entity, got {type(other)}"
            raise TypeError(msg)
        if self.uid != other.uid:
            msg = f"Cannot compare versions of entities with different UIDs: {self.uid} vs {other.uid}"
            raise ValueError(msg)
        return self.version > other.version

    @computed_field(description="Indicates whether this entity instance has been superseded by another instance with an incremented version.")
    @property
    def superseded(self) -> bool:
        """Indicates whether this entity instance has been superseded by another instance with an incremented version."""
        return self.entity_log.version > self.version

    @property
    def superseding_or_none[T: Entity](self: T) -> T | None:
        if not self.superseded:
            return self
        return type(self).by_uid_or_none(self.uid)

    @property
    def superseding[T: Entity](self: T) -> T:
        if (result := self.superseding_or_none) is None:
            msg = f"Entity {self} has been superseded but the superseding entity could not be found."
            raise ValueError(msg)
        return result

    def update[T: Entity](self: T, **kwargs: Any) -> T:
        """Create a new instance of the entity with the updated data.

        The new instance will have an incremented version and the same UID, superseding the current instance.
        """
        # Check if we are in the middle of a commit
        if not self.is_update_allowed():
            msg = f"Not allowed to update {type(self).__name__} instances outside of a session commit."
            raise RuntimeError(msg)

        # Validate data
        if not kwargs:
            msg = "No data provided to update the entity."
            raise ValueError(msg)

        if "uid" in kwargs:
            msg = "Cannot update the 'uid' of an entity. The UID is immutable and should not be changed."
            raise ValueError(msg)
        if "version" in kwargs:
            msg = "Cannot update the 'version' of an entity. The version is managed by the entity itself and should not be changed directly."
            raise ValueError(msg)
        if "entity_links" in kwargs:
            msg = "Cannot update the 'entity_links' of an entity. The links are managed by the entity itself and should not be changed directly."
            raise ValueError(msg)

        args = {}
        for field_name in type(self).model_fields:
            target_name = self.reverse_field_alias(field_name)
            if field_name in kwargs:
                args[target_name] = kwargs[field_name]
            else:
                args[target_name] = getattr(self, field_name)

        args.update(kwargs)
        args["uid"] = self.uid
        args["version"] = self.entity_log.next_version

        # Sanity check - name won't change
        if (new_name := self.calculate_instance_name_from_dict(args)) != self.instance_name:
            msg = f"Updating the entity cannot change its instance name. Original: '{self.instance_name}', New: '{new_name}'."
            raise ValueError(msg)

        # Update entity
        new_entity = type(self)(**args)

        # Sanity check - name didn't change
        if not isinstance(new_entity, type(self)):
            msg = f"Expected new entity to be an instance of {type(self).__name__}, got {type(new_entity).__name__}."
            raise TypeError(msg)
        if new_entity.instance_name != self.instance_name:
            msg = f"Updating the entity cannot change its instance name. Original: '{self.instance_name}', New: '{new_entity.instance_name}'."
            raise ValueError(msg)

        # Return updated entity
        return new_entity

    # MARK: Session / Journal
    @property
    def session_manager_or_none(self) -> SessionManager | None:
        from ...journal.session_manager import SessionManager

        return SessionManager.get_global_manager_or_none()

    @property
    def session_manager(self) -> SessionManager:
        from ...journal.session_manager import SessionManager

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

    get_journal_class = generics.GenericIntrospectionMethod[T_Journal]()

    def get_journal(self, *, create: bool = True, fail: bool = True) -> EntityJournal | None:
        session = self.session if fail else self.session_or_none
        return session.get_entity_journal(entity=self, create=create) if session is not None else None

    @property
    def journal(self) -> T_Journal:
        result = self.get_journal(create=True)
        if result is None:
            msg = f"No journal found for entity {self}."
            raise RuntimeError(msg)
        journal_cls = self.get_journal_class()
        if type(result) is not journal_cls:
            msg = f"Expected journal of type {journal_cls}, got {type(result)}."
            raise RuntimeError(msg)
        return result

    @property
    def has_journal(self) -> bool:
        return self.get_journal(create=False) is not None

    @staticmethod
    def _is_entity_attribute(name: str) -> bool:
        return hasattr(Entity, name) or name in Entity.model_fields or name in Entity.model_computed_fields

    @classmethod
    def is_model_field_alias(cls, alias: str) -> bool:
        return cls.model_field_aliases.get(alias, None) is not None

    @classmethod
    def resolve_field_alias(cls, alias: str) -> str:
        return cls.model_field_aliases.get(alias, alias)

    @classmethod
    def reverse_field_alias(cls, name: str) -> str:
        return cls.model_field_reverse_aliases.get(name, name)

    @classmethod
    def is_model_field(cls, field: str) -> bool:
        return field in cls.model_fields

    @classmethod
    def is_computed_field(cls, field: str) -> bool:
        return field in cls.model_computed_fields

    @property
    def dirty(self) -> bool:
        j = self.get_journal(create=False)
        return j.dirty if j is not None else False

    @property
    def in_session(self) -> bool:
        try:
            manager = self.session_manager
        except (TypeError, AttributeError, KeyError):
            return False
        return manager.in_session

    def is_journal_field_edited(self, field: str) -> bool:
        journal = self.get_journal(create=False)
        return journal.is_field_edited(field) if journal is not None else False

    def get_journal_field(self, field: str, *, create: bool = True, wrap: bool = True) -> Any:
        journal = self.get_journal(create=create)
        if journal is None or (not wrap and not journal.is_field_edited(field)):
            return getattr(self, field)
        else:
            assert wrap
            return journal.get_field(field, wrap=True)

    _PROTECTED_FIELD_TYPES: ClassVar[tuple[type, ...]]

    @classmethod
    def _get_protected_field_types(cls) -> tuple[type, ...]:
        s = getattr(Entity, "_PROTECTED_FIELD_TYPES", None)
        if s is not None:
            return s

        from ...collections import JournalledCollection, OrderedViewMutableSet

        default = (JournalledCollection, OrderedViewMutableSet, OrderedViewMutableSet, EntityAuditLog, EntityDependents)
        setattr(Entity, "_PROTECTED_FIELD_TYPES", default)
        return default

    @classmethod
    def _get_field_annotation(cls, field: str) -> Any | None:
        for mro in cls.__mro__:
            annotations = annotationlib.get_annotations(mro, format=annotationlib.Format.VALUE)
            annotation = annotations.get(field, None)
            if annotation is not None:
                return annotation
        return None

    _PROTECTED_FIELD_LOOKUP: ClassVar[MutableMapping[str, bool]]

    @classmethod
    def is_protected_field_type(cls, field: str) -> bool:
        protected_field_lookup = getattr(cls, "_PROTECTED_FIELD_LOOKUP", None)
        if protected_field_lookup is None:
            protected_field_lookup = cls._PROTECTED_FIELD_LOOKUP = {}
        elif (result := protected_field_lookup.get(field)) is not None:
            return result

        annotation = cls._get_field_annotation(field)
        if annotation is None:
            msg = f"Field '{field}' not found in entity type {cls.__name__} annotations."
            raise RuntimeError(msg)

        forbidden_types = cls._get_protected_field_types()
        result = False
        for hint in type_hints.iterate_type_hints(annotation):
            origin = generics.get_origin(hint, passthrough=True)
            if issubclass(origin, forbidden_types):
                result = True
                break

        protected_field_lookup[field] = result
        return result

    # MARK: Proxy
    @classmethod
    def get_proxy_class(cls) -> type[T_Proxy]:
        if (proxy_cls := PROXY_TYPES.get(cls, None)) is None:
            if not issubclass(cls, Entity):
                msg = "Cannot get proxy class for abstract base Entity class. Please use a concrete subclass."
                raise RuntimeError(msg)
            return super().get_proxy_class()  # pyright: ignore[reportAttributeAccessIssue]

        from .entity_proxy import EntityProxy

        assert issubclass(proxy_cls, EntityProxy)
        return typing_cast("type[T_Proxy]", proxy_cls)

    @classmethod
    def register_proxy_class(cls, proxy_cls: type[T_Proxy]) -> None:
        from .entity_proxy import EntityProxy

        if not issubclass(proxy_cls, EntityProxy):
            msg = f"Proxy class must be a subclass of EntityProxy, got {proxy_cls.__name__}."
            raise TypeError(msg)

        if cls in PROXY_TYPES:
            msg = f"Proxy class for entity type {cls.__name__} is already registered as {PROXY_TYPES[cls].__name__}."
            raise RuntimeError(msg)

        PROXY_TYPES[cls] = proxy_cls

        # Register with ABCMeta
        Entity.register(proxy_cls)

    _proxy: WeakRef[T_Proxy] | None = PrivateAttr(default=None)

    @property
    def proxy(self) -> T_Proxy:
        proxy = self._proxy
        if proxy is not None:
            proxy = proxy()
        if proxy is not None:
            return proxy

        proxy_cls = self.get_proxy_class()
        proxy = proxy_cls(self, create=True)
        self._proxy = weakref.ref(proxy)
        return proxy

    # MARK: Children
    # These are all entities that are considered reachable (and therefore not garbage collected) by the existence of this entity.
    # I.e. those referenced by fields in the entity as well as annotations.
    def _get_children_field_ignore(self, field_name: str) -> bool:
        return field_name.startswith("_") or field_name in ("uid", "extra_dependency_uids")

    def iter_children_uids(self, *, use_journal: bool = False) -> Iterable[Uid]:
        # Inspect all fields of the entity for UIDs or Entities
        for attr in type(self).model_fields:
            if self._get_children_field_ignore(attr):
                continue

            if use_journal and (journal := self.get_journal(create=False)) is not None and journal.is_field_edited(attr):
                value = getattr(journal, attr, None)
            else:
                value = getattr(self, attr, None)

            if value is None:
                continue

            if isinstance(value, Uid):
                yield value
            elif isinstance(value, Entity):
                yield value.uid
            elif isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
                for item in value:
                    if isinstance(item, Uid):
                        yield item
                    elif isinstance(item, Entity):
                        yield item.uid

    @cached_property
    def children_uids(self) -> Iterable[Uid]:
        return frozenset(self.iter_children_uids())

    @property
    def journal_children_uids(self) -> Iterable[Uid]:
        journal = self.get_journal(create=False)
        return self.children_uids if journal is None else journal.children_uids

    def get_children_uids(self, *, use_journal: bool = False) -> Iterable[Uid]:
        return self.journal_children_uids if use_journal else self.children_uids

    @property
    def children(self) -> Iterable[Entity]:
        for uid in self.children_uids:
            yield Entity.by_uid(uid)

    def iter_hierarchy(
        self, *, condition: Callable[[Entity], bool] | None = None, use_journal: bool = False, check_condition_on_return: bool = True
    ) -> Iterable[Entity]:
        """Return a flat ordered set of all entities in this hierarchy."""
        if condition is not None and not condition(self):
            return

        # Iterate dirty children journals
        for uid in self.get_children_uids(use_journal=use_journal):
            child = Entity.by_uid_or_none(uid)
            if child is None:
                continue

            if condition is not None and not condition(child):
                continue

            yield from child.iter_hierarchy(condition=condition, use_journal=use_journal, check_condition_on_return=check_condition_on_return)

        if check_condition_on_return and condition is not None and not condition(self):
            msg = f"Entity {self} failed condition check on return of yield_hierarchy."
            raise RuntimeError(msg)

        # Yield self, then return
        yield self

    def is_reachable(self, *, recursive: bool = True, use_journal: bool = False) -> bool:
        from ..root import EntityRoot

        parent = self.instance_parent
        if parent is None:
            msg = f"Entity {self} has no parent, cannot determine reachability."
            raise ValueError(msg)
        if isinstance(parent, EntityRoot):
            return True
        if not isinstance(parent, Entity):
            msg = f"Entity {self} has a parent of type {type(parent).__name__}, expected Entity or EntityRoot."
            raise TypeError(msg)

        # Check if parent contains us
        iterable = parent.children_uids if not use_journal else parent.journal_children_uids
        if self.uid not in iterable:
            return False

        # Recurse up the tree
        if not recursive:
            return True
        else:
            return parent.is_reachable(use_journal=use_journal, recursive=True)

    # MARK: Annotations
    @property
    def annotations(self) -> UidProxySet[Entity]:
        from ...collections.uid_proxy import UidProxySet

        return UidProxySet[Entity](instance=self, field="annotation_uids")

    def on_annotation_created(self, annotation_or_uid: Annotation | Uid) -> None:
        if not self.is_update_allowed(in_commit_only=False, force_session=True):
            msg = f"Not allowed to modify annotations of {type(self).__name__} instances outside of a session."
            raise RuntimeError(msg)

        from ..annotation import Annotation

        uid = Annotation.narrow_to_uid(annotation_or_uid)
        if uid in self.journal.annotation_uids:
            return

        self.journal.annotation_uids.add(uid)

    def on_annotation_deleted(self, annotation_or_uid: Annotation | Uid) -> None:
        self.log.debug(t"Entity {self} received deletion notice for annotation {annotation_or_uid}.")

        if not self.is_update_allowed(in_commit_only=False, force_session=True):
            msg = f"Not allowed to modify annotations of {type(self).__name__} instances outside of a session."
            raise RuntimeError(msg)

        from ..annotation import Annotation

        uid = Annotation.narrow_to_uid(annotation_or_uid)
        if uid not in self.journal.annotation_uids:
            return

        self.journal.annotation_uids.discard(uid)

    # MARK: Dependents
    entity_dependents: EntityDependents = Field(
        default_factory=lambda data: EntityDependents(data["uid"]),
        validate_default=True,
        repr=False,
        exclude=True,
        description="The dependents of this entity, which tracks other entities that depend on this entity.",
    )

    @property
    def dependent_uids(self) -> Iterable[Uid]:
        return self.entity_dependents.dependent_uids

    @property
    def dependents(self) -> Iterable[Entity]:
        return self.entity_dependents.dependents

    # MARK: Dependencies
    @property
    def extra_dependencies(self) -> UidProxySet[Entity]:
        from ...collections.uid_proxy import UidProxySet

        return UidProxySet[Entity](instance=self, field="extra_dependency_uids")

    # MARK: Dependency Events
    __entity_dependency_event_handler_records__: ClassVar[MutableSet[EntityDependencyEventHandlerRecord]]

    @classmethod
    def __init_dependencies__(cls) -> None:
        cls.__entity_dependency_event_handler_records__ = set()

    @classmethod
    def register_dependency_event_handler(cls, record: EntityDependencyEventHandlerRecord) -> None:
        cls.__entity_dependency_event_handler_records__.add(record)

    if script_info.is_unit_test():

        @classmethod
        def clear_dependency_event_handlers(cls) -> None:
            if hasattr(cls, "__entity_dependency_event_handler_records__"):
                cls.__entity_dependency_event_handler_records__.clear()
                cls.__init_dependencies__()

            for t in ENTITY_SUBCLASSES:
                if issubclass(t, cls):
                    if hasattr(t, "__entity_dependency_event_handler_records__"):
                        t.__entity_dependency_event_handler_records__.clear()
                        t.__init_dependencies__()

    @classmethod
    def iter_dependency_event_handlers(cls) -> Iterable[EntityDependencyEventHandlerRecord]:
        for subclass in cls.__mro__:
            if not issubclass(subclass, Entity):
                continue
            if not hasattr(subclass, "__entity_dependency_event_handler_records__"):
                continue
            yield from subclass.__entity_dependency_event_handler_records__

    def _call_dependency_event_handlers(self, event: EntityDependencyEventType, entity: Entity, journal: EntityJournal) -> bool:
        matched = False
        for record in type(self).iter_dependency_event_handlers():
            matched_current = record(owner=self, event=event, entity=entity, journal=journal)
            matched |= matched_current

            # Abort if one of the handlers marks this entity for deletion
            if matched_current and self.marked_for_deletion:
                break
        return matched

    def on_dependency_updated(self, source: EntityJournal) -> None:
        entity = source.entity

        self.log.debug(t"Entity {self} received invalidation from dependency entity {entity}.")

        # Propagate the update to any fields that reference the source entity
        self._propagate_dependency_update(source)

        # Call event handlers
        self._call_dependency_event_handlers(event=EntityDependencyEventType.UPDATED, entity=entity, journal=source)

    def _propagate_dependency_update(self, source: EntityJournal) -> None:
        from ...collections import HasJournalledTypeCollectionProtocol, OnItemUpdatedCollectionProtocol

        uid = source.uid
        entity = source.entity

        # Loop through entity fields, and search for OrderedViewMutableSets that referenced the source entity
        for nm in type(self).model_fields:
            original = getattr(self, nm, None)
            if original is None:
                continue

            elif original is entity:
                # Direct reference to the entity
                value = self.journal.get_field(nm, wrap=True)
                if value is not entity:
                    continue

                self.log.debug("Propagating dependency %s update to field '%s'", source.entity, nm)
                self.journal.set_field(nm, entity)

            elif isinstance(original, HasJournalledTypeCollectionProtocol):
                edited = self.is_journal_field_edited(nm)
                value = self.journal.get_field(nm, wrap=False) if edited else original

                # Only propagate if the invalidated child is present in both the wrapped set *and* the original set
                # (this avoids propagating invalidations for items that have been added or removed from the set in the same session as the invalidation)
                if uid not in original or (value is not original and uid not in value):
                    continue

                if not edited:
                    value = self.journal.get_field(nm, wrap=True)
                assert isinstance(value, OnItemUpdatedCollectionProtocol), f"Expected OnItemUpdatedCollectionProtocol, got {type(value)}"
                assert uid in value

                self.log.debug("Propagating dependency %s update to collection '%s'", source.entity, nm)
                value.on_item_updated(entity, source)

    def on_dependency_deleted(self, source: EntityJournal) -> None:
        entity = source.entity

        self.log.debug(t"Entity {self} received deletion notice from dependency entity {entity}.")

        # If the entity is the parent of this entity, then we should delete ourselves too
        if (parent := self.entity_parent_or_none) is not None and parent.uid == entity.uid:
            self.log.warning(t"Entity {self} is a child of deleted entity {entity}, deleting itself too.")
            self.delete()
            return

        # Sanity check: Entity cannot be the parent of this entity
        if entity is self.entity_parent_or_none:
            msg = f"Entity {entity} is the parent of {self} and cannot be deleted without deleting the child first."
            raise RuntimeError(msg)

        # Sanity check: Entity cannot be a child of this entity
        if entity.uid in self.journal_children_uids:
            if self.is_reachable(use_journal=True):
                msg = f"Entity {entity} is a child of {self} and cannot be deleted."
                raise RuntimeError(msg)
            else:
                # TODO: As part of _propagate_delete, entities should try to remove themselves from their parent.
                #       This is hack here to handle the situation where they don't.
                self.log.warning(t"Entity {self} is no longer reachable, but is not deleted. Marking for deletion.")
                self.delete()
                return

        # Call event handlers
        self._call_dependency_event_handlers(event=EntityDependencyEventType.DELETED, entity=entity, journal=source)
        if self.marked_for_deletion:
            return

        # If the entity is in our extra dependencies, we remove it
        if entity.uid in self.extra_dependency_uids:
            self.journal.remove_dependency(entity.uid)

    # MARK: Utilities
    def sort_key(self) -> SupportsRichComparison:
        return self.uid

    @override
    def __hash__(self) -> int:
        return hash((self.uid, self.version))

    @override
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Entity):
            return self.uid == other.uid and self.version == other.version
        else:
            return False

    @override
    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    @override
    def __str__(self) -> str:
        version = getattr(self, "version", "?")
        return super().__str__().replace(">", f" v{version}>")

    @override
    def __repr__(self) -> str:
        version = getattr(self, "version", "?")
        return super().__repr__().replace(">", f" v{version}>")
