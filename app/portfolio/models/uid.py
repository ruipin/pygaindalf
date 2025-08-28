# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import random
import sys
import re

from dataclasses import dataclass, field

from typing import Protocol, override, Hashable, runtime_checkable, ClassVar, Self, Any
from pydantic import BaseModel, Field, model_validator, ModelWrapValidatorHandler
from abc import ABCMeta, abstractmethod

from ...util.helpers import classproperty
from ...util.mixins import NamedMixinMinimal, NamedProtocol, NamedMutableProtocol
from ...util.helpers import script_info


UID_SEPARATOR = '#'
UID_ID_REGEX = re.compile(r'^[a-zA-Z0-9@_-]+$')


# MARK: Uid Class
@dataclass(frozen=True, slots=True)
class Uid:
    namespace: str = "DEFAULT"
    id: Hashable = field(default_factory=lambda: random.getrandbits(sys.hash_info.width))

    def __post_init__(self):
        if not self.namespace or not isinstance(self.namespace, str):
            raise ValueError("Namespace must be a non-empty string.")
        if re.search(UID_ID_REGEX, self.namespace) is None:
            raise ValueError(f"ID '{self.namespace}' is not valid. It must match the pattern '{UID_ID_REGEX.pattern}'.")

        if self.id is None:
            raise ValueError("ID must be an integer or string.")
        if re.search(UID_ID_REGEX, self.id_as_str) is None:
            raise ValueError(f"ID '{self.id}' is not valid. When converted to string, it must match the pattern '{UID_ID_REGEX.pattern}'.")

    def as_tuple(self):
        return (self.namespace, self.id)

    @property
    def id_as_str(self) -> str:
        """Returns the ID as a string, suitable for display."""
        if isinstance(self.id, int):
            return format(self.id, 'x')
        else:
            return str(self.id)

    @override
    def __hash__(self):
        return hash(self.as_tuple())

    @override
    def __eq__(self, other):
        if not isinstance(other, Uid):
            return False
        return self.as_tuple() == other.as_tuple()

    @override
    def __ne__(self, other):
        return not self.__eq__(other)

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

    def next(self, namespace: str, increment : bool = True) -> Uid:
        # Warning: This method is not thread-safe.
        counter = self.counters.get(namespace, 1)
        uid = Uid(namespace=namespace, id=counter)
        if increment:
            self.counters[namespace] = counter + 1
        return uid

    if script_info.is_unit_test():
        def reset(self) -> None:
            self.counters.clear()


# MARK: Protocol
@runtime_checkable
class UidProtocol(Protocol):
    @property
    def uid(self) -> Uid: ...