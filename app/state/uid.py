# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import random
import sys

from dataclasses import dataclass, field

from typing import Protocol, override, Hashable, runtime_checkable, ClassVar
from pydantic import BaseModel
from abc import ABCMeta, abstractmethod

from ..util.helpers import classproperty
from ..util.mixins import NamedMixinMinimal, NamedProtocol, NamedMutableProtocol


UID_SEPARATOR = '-'


# MARK: Uid Class
@dataclass(frozen=True, slots=True)
class Uid:
    namespace: str = "DEFAULT"
    id: Hashable = field(default_factory=lambda: random.getrandbits(sys.hash_info.width))

    def as_tuple(self):
        return (self.namespace, self.id)

    def __post_init__(self):
        if not self.namespace:
            raise ValueError("Namespace cannot be empty.")
        if ' ' in self.namespace:
            raise ValueError("Namespace cannot contain spaces.")

    @override
    def __hash__(self):
        return hash(self.as_tuple())

    @override
    def __eq__(self, other):
        if not isinstance(other, Uid):
            raise TypeError(f"Cannot compare Uid with {type(other).__name__}")
        return self.as_tuple() == other.as_tuple()

    @override
    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def id_as_str(self) -> str:
        """Returns the ID as a string, suitable for display."""
        if isinstance(self.id, int):
            return format(self.id, 'x')
        else:
            return str(self.id)

    @override
    def __str__(self):
        return f"{self.namespace}{UID_SEPARATOR}{self.id_as_str}"

    @override
    def __repr__(self):
        return f"Uid(namespace={self.namespace}, id={self.id})"


# MARK: Incrementing Uid Factory
class IncrementingUidFactory:
    _instance : ClassVar['IncrementingUidFactory']
    counters : dict[str, int]

    def __new__(cls, namespace: str = 'DEFAULT'):
        instance = getattr(cls, '_instance', None)
        if not instance:
            instance = cls._instance = super(IncrementingUidFactory, cls).__new__(cls)
        return instance

    def __init__(self):
        # Ensure singleton behavior for each namespace
        if not hasattr(self, 'namespace'):
            self.counters = dict()

    def next(self, namespace: str) -> Uid:
        # Warning: This method is not thread-safe.
        counter = self.counters.get(namespace, 1)
        uid = Uid(namespace=namespace, id=counter)
        self.counters[namespace] = counter + 1
        return uid


# MARK: Protocol
@runtime_checkable
class UidProtocol(Protocol):
    @property
    def uid(self) -> Uid: ...


# MARK: Minimal Uid Mixin
class UidMixinMinimal(metaclass=ABCMeta):
    UID_INIT_KWARG_ALLOWED : ClassVar[bool] = True

    def __init__(self, *args, **kwargs):
        uid = kwargs.pop('uid', None)
        if uid is not None and not self.UID_INIT_KWARG_ALLOWED:
            raise ValueError(f"{self.__class__.__name__} does not allow 'uid' as an init keyword argument.")

        super().__init__(*args, **kwargs)

        # Read UID property to ensure it is immediately calculated
        if self.__dict__.get('uid', None) is None:
            calculate_uid_kwargs = {}
            if uid is not None:
                calculate_uid_kwargs['uid'] = uid
            uid = self._calculate_uid(**calculate_uid_kwargs)
            self.__dict__['uid'] = uid

    @property
    def uid(self) -> Uid:
        return self.__dict__['uid']

    @property
    def uid_namespace(self) -> str:
        """
        Returns the namespace for the UID.
        This can be overridden in subclasses to provide a custom namespace.
        """
        return self.__class__.__name__

    def _calculate_uid(self, *, uid : Uid | None = None) -> Uid:
        if uid is None:
            raise ValueError(f"UID cannot be None")
        return uid


# MARK: Mixins
class IncrementingUidMixin(UidMixinMinimal):
    """
    A mixin for classes that require an incrementing UID.
    """
    UID_INIT_KWARG_ALLOWED : ClassVar[bool] = False

    uid_factory : ClassVar[IncrementingUidFactory]

    def __init_subclass__(cls) -> None:
        """
        Initialize the mixin for subclasses.
        This ensures that the UID factory is created only once per class.
        """
        if getattr(cls, 'uid_factory', None) is None:
            cls.uid_factory = IncrementingUidFactory()

    @override
    def _calculate_uid(self, *, uid : Uid | None = None) -> Uid:
        """
        Returns a Uid instance based on the class's UID_NAME_ATTRIBUTE.
        """
        return self.__class__.uid_factory.next(self.uid_namespace)

    @property
    def instance_name(self) -> str:
        """
        Returns the name of the instance.
        This can be overridden in subclasses to provide a custom name.
        """
        return str(self.uid)

    @instance_name.setter
    def instance_name(self, new_name : str | None) -> None:
        raise ValueError(f"Cannot set instance_name for {self.__class__.__name__}. It is derived from the UID.")


class NamedUidMixin(UidMixinMinimal):
    """
    A mixin for creating Uids for NamedProtocol classes, based on the instance name (or hierarchical name in case of HierarchicalProtocol).
    This is useful for cases where your class already has a unique name attribute.
    """
    @override
    def _calculate_uid(self, *, uid : Uid | None = None) -> Uid:
        """
        Returns a Uid instance based on the class's UID_NAME_ATTRIBUTE.
        """
        if not isinstance(self, (NamedMutableProtocol, NamedMixinMinimal)):
            raise TypeError(f"{self.__class__.__name__} must implement NamedProtocol to use NamedUidMixin.")

        if self.is_instance_name_default():
            raise ValueError(f"{self.__class__.__name__} must not have the default instance name when calculating its UID. Please set instance_name before using NamedUidMixin.")

        return Uid(namespace=self.uid_namespace, id=self.instance_name)