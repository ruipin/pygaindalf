# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Any, Self, override
from typing import cast as typing_cast

from ....util.helpers import mro
from ....util.mixins import NamedProtocol
from .entity import Entity


if TYPE_CHECKING:
    from app.portfolio.models.store.string_uid_mapping import StringUidMapping

    from ...util import Uid
    from ..store.entity_store import EntityStore
    from .entity_log import EntityLog


class InstanceStoreMixin(metaclass=ABCMeta):
    # MARK: Type hints for entity attributes and methods that we rely on
    if TYPE_CHECKING:
        uid: Uid
        entity_log: EntityLog

        @classmethod
        def _get_entity_store(cls) -> EntityStore: ...
        @property
        def initialized(self) -> bool: ...
        @property
        def exists(self) -> bool: ...

    # MARK: Construction / metaclassing
    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        mro.ensure_mro_order(cls, InstanceStoreMixin, before=Entity)

    # MARK: Abstract Methods
    @classmethod
    @abstractmethod
    def _instance_store_search(cls, **kwargs) -> Self | None:
        msg = "This method should be implemented by subclasses to find an existing instance based on the provided kwargs."
        raise NotImplementedError(msg)

    @classmethod
    @abstractmethod
    def _instance_store_add(cls, instance: Self) -> None:
        msg = "This method should be implemented by subclasses to add an instance to the store."
        raise NotImplementedError(msg)

    # MARK: Create instance
    def __new__(cls, **kwargs) -> Self:
        if (instance := cls._instance_store_search(**kwargs)) is None:
            instance = super().__new__(cls, **kwargs)
        else:
            instance._on_reinit(**kwargs)
        return instance

    # MARK: Handle (re-)initialization
    def __init__(self, **kwargs) -> None:
        initialized = self.initialized

        super().__init__(**kwargs)

        if not initialized:
            self._instance_store_add(self)

    def _on_reinit(self, **data) -> None:
        if self.exists:
            for k, v in data.items():
                cur = self.record.__dict__.get(k, None)  # pyright: ignore[reportAttributeAccessIssue]
                if cur is not v:
                    msg = f"Expected '{k}' value '{cur}' but got '{v}'."
                    raise ValueError(msg)

        super()._on_reinit(**data)  # pyright: ignore[reportAttributeAccessIssue]


# MARK: Mixin for Named Instances
class NamedInstanceStoreMixin(InstanceStoreMixin, metaclass=ABCMeta):
    @classmethod
    def _get_name_store(cls) -> StringUidMapping:
        return cls._get_entity_store().get_string_uid_mapping(cls.__name__)

    @classmethod
    @override
    def _instance_store_search(cls, **kwargs) -> Self | None:
        instance_name = cls.calculate_instance_name_from_dict(kwargs)
        if instance_name is None:
            return None

        return cls.instance(instance_name)

    @classmethod
    @override
    def _instance_store_add(cls, instance: Self) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        if not isinstance(instance, NamedProtocol):
            msg = f"Expected an instance of a class implementing NamedProtocol, got {type(instance).__name__}."
            raise TypeError(msg)
        if (name := instance.instance_name) is None:
            msg = f"{cls.__name__} must have a valid 'instance_name' to be added to the instance store."
            raise ValueError(msg)
        cls._get_name_store()[name] = instance.uid

    @classmethod
    def instance(cls, instance_name: str) -> Self | None:
        return typing_cast("Self | None", cls._get_name_store().get_entity(instance_name, fail=False))

    @classmethod
    @abstractmethod
    def calculate_instance_name_from_dict(cls, data: dict[str, Any]) -> str:
        msg = f"{cls.__name__} must implement the 'calculate_instance_name_from_dict' method to generate a name for the instance."
        raise NotImplementedError(msg)
