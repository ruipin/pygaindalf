# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import MutableSet
from ordered_set import OrderedSet
from dataclasses import is_dataclass, asdict as dataclass_asdict
from typing import Iterator, override, Any, runtime_checkable, Protocol

from .namespace import Namespace
from ..mixins import *
from ..enter_exit_call import EnterExitCall, Iterable


class NamespaceSet[T](Namespace, MutableSet[T], metaclass=ABCMeta):
    """
    A set wrapper with extended functionality, supporting both set and namespace behaviors.

    Provides a mutable set with attribute access, freezing, and mixin support. Used for unique collections
    of configuration or data objects in pygaindalf.
    """

    def __init__(self, *args, frozen_schema=False, frozen_namespace=False, frozen_set=False, **kwargs):
        """
        Initializes a NamespaceSet instance.

        Args:
            frozen_schema (bool): If True, freeze the schema.
            frozen_namespace (bool): If True, freeze the namespace.
            frozen_set (bool): If True, freeze the set.
            *args: Positional arguments for set initialization.
            **kwargs: Keyword arguments for set initialization.
        """
        # Call super-class
        super_params = {}
        if isinstance(self, LoggableMixin):
            super_params['instance_name'] = kwargs.pop('instance_name', None)
        if isinstance(self, HierarchicalMixin):
            super_params['instance_parent'] = kwargs.pop('instance_parent', None)
        super().__init__(frozen_schema=frozen_schema, frozen_namespace=frozen_namespace, **super_params)

        self.__frozen_set : bool = False

        self._set = OrderedSet(*args, **kwargs)

        self.__frozen_set = frozen_set


    # MARK: Abstract methods implementation
    @override
    def add(self, value) -> None:
        """
        Adds an element to the set.

        Args:
            value: The element to add.

        Raises:
            RuntimeError: If the set is frozen.
        """
        if self.frozen_set:
            raise RuntimeError(f"{self.__class__.__name__} is frozen")
        self._set.add(value)

    @override
    def discard(self, value) -> None:
        """
        Removes an element from the set if it exists.

        Args:
            value: The element to remove.

        Raises:
            RuntimeError: If the set is frozen.
        """
        if self.frozen_set:
            raise RuntimeError(f"{self.__class__.__name__} is frozen")
        self._set.discard(value)

    @override
    def __len__(self) -> int:
        """
        Returns the number of elements in the set.

        Returns:
            int: The number of elements in the set.
        """
        return len(self._set)

    @override
    def __iter__(self) -> Iterable[T]: # pyright: ignore[reportIncompatibleMethodOverride]
        """
        Returns an iterator over the set.

        Returns:
            iterator: An iterator over the set.
        """
        return iter(self._set)

    @override
    def __contains__(self, m : object) -> bool:
        """
        Checks if an element is in the set.

        Args:
            m: The element to check.

        Returns:
            bool: True if the element is in the set, False otherwise.
        """
        return m in self._set


    def replace(self, other_set) -> None:
        """
        Replaces the current set with another set.

        Args:
            other_set (set): The set to replace with.

        Raises:
            RuntimeError: If the set is frozen.
        """
        if self.frozen_set:
            raise RuntimeError(f"{self.__class__.__name__} is frozen")

        self._set : OrderedSet[T] = OrderedSet(other_set)


    # MARK: Freezing - Set
    @runtime_checkable
    class FreezableSetProtocol(Protocol):
        @property
        def frozen_set(self) -> bool: ...
        @frozen_set.setter
        def frozen_set(self, val:bool) -> None: ...
        def freeze_set(self, freeze:bool=True, *, temporary:bool=False) -> EnterExitCall|None: ...
        def unfreeze_set(self, recursive:bool=False, temporary:bool=False) -> EnterExitCall|None: ...

    def freeze_set(self, freeze=True, *, temporary=False) -> EnterExitCall|None:
        """
        Freezes or unfreezes the set.

        Args:
            freeze (bool): If True, freeze the set. If False, unfreeze the set.
            temporary (bool): If True, apply the freeze/unfreeze operation temporarily.

        Returns:
            EnterExitCall: Context manager for temporary freeze/unfreeze.
        """
        if temporary:
            return EnterExitCall(
                self.freeze_set, self.freeze_set,
                kwargs_enter={'freeze': freeze, 'temporary': False},
                kwargs_exit={'freeze': not freeze, 'temporary': False})

        self.__frozen_set = freeze

    def unfreeze_set(self, temporary=False) -> EnterExitCall|None:
        """
        Unfreezes the set.

        Args:
            temporary (bool): If True, apply the unfreeze operation temporarily.

        Returns:
            EnterExitCall: Context manager for temporary unfreeze.
        """
        return self.freeze_set(False, temporary=temporary)

    @property
    def frozen_set(self) -> bool:
        """
        Indicates whether the set is frozen.

        Returns:
            bool: True if the set is frozen, False otherwise.
        """
        return self.__frozen_set

    @frozen_set.setter
    def frozen_set(self, val) -> None:
        """
        Sets the frozen state of the set.

        Args:
            val (bool): The frozen state to set.
        """
        self.freeze_set(val, temporary=False)


    # MARK: Type conversion
    def asset(self, recursive=True, private=False, protected=True, public=True) -> set[T]:
        """
        Returns the set as a collection of assets.

        Args:
            recursive (bool): If True, include nested assets.
            private (bool): If True, include private attributes.
            protected (bool): If True, include protected attributes.
            public (bool): If True, include public attributes.

        Returns:
            set: The set as a collection of assets.
        """
        if not recursive:
            return set(self._set)

        s = set()
        for v in self._set:

            if isinstance(v, Namespace):
                v = v.asdict(recursive=recursive, private=private, protected=protected, public=public)

            if not private and is_dataclass(v) and not isinstance(v, type):
                v = dataclass_asdict(v)

            s.add(v)

        return s

    @override
    def asdict(self, recursive=True, private=False, protected=True, public=True) -> dict:
        """
        Returns the set as a dictionary.

        Args:
            recursive (bool): If True, include nested dictionaries.
            private (bool): If True, include private attributes.
            protected (bool): If True, include protected attributes.
            public (bool): If True, include public attributes.

        Returns:
            dict: The set as a dictionary.
        """
        d = super().asdict(recursive=recursive, private=private, protected=protected, public=public)

        if not recursive:
            return d

        d['_set'] = self.asset(recursive=recursive, private=private, protected=protected, public=public)
        return d


    # MARK: Printing
    @override
    def __repr__(self):
        """
        Returns a string representation of the set.

        Returns:
            str: A string representation of the set.
        """
        return f"<{self._Namespace__repr_name}:{repr(self.asset(recursive=False))}>"
