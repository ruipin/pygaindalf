# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from abc import ABCMeta
from collections.abc import ItemsView, KeysView, MutableMapping, ValuesView
from dataclasses import is_dataclass, asdict as dataclass_asdict
from typing import Any, Self, override, Iterable, runtime_checkable, Protocol

from . import Namespace
from .. import LoggableMixin, HierarchicalMixin, NamedMixin
from ..enter_exit_call import EnterExitCall


class NamespaceMap[K = str, V = Any](Namespace, MutableMapping[K,V], metaclass=ABCMeta):
    """
    A namespace that behaves like a dictionary or object, allowing both attribute and key-based access.

    Extends Namespace to provide a mapping interface, with support for freezing, merging, and mixin extensions.
    Used for structured configuration and data storage in pygaindalf.
    """

    # We want to hide some attributes from the dictionary
    # NOTE: We include the log/parent attributes here just in case someone decides to make this class Loggable or Hierarchical
    __slots__ = {'_NamespaceMap__frozen_map', '_dict'}

    # MARK: Constructor
    def __init__(self, *, frozen_schema=False, frozen_namespace=False, frozen_map=False, **kwargs):
        """
        Initialize a NamespaceMap instance.

        Args:
            frozen_schema (bool): If True, freeze the schema (no new keys allowed).
            frozen_namespace (bool): If True, freeze the namespace (no changes allowed).
            frozen_map (bool): If True, freeze the mapping (no changes allowed).
            **kwargs: Initial key-value pairs to populate the namespace map.
        """

        self._dict : dict[K,V] = {}

        # Call super-class
        super_params: Namespace.DictView = {}
        if isinstance(self, NamedMixin):
            super_params['instance_name'] = kwargs.pop('instance_name', None)
        if isinstance(self, HierarchicalMixin):
            super_params['instance_parent'] = kwargs.pop('instance_parent', None)
        super().__init__(frozen_schema=frozen_schema, frozen_namespace=frozen_namespace, **super_params)

        # Initialize basic state
        self.__frozen_map : bool = False

        # Finish initialization
        self.merge(kwargs)

        self.__frozen_map = frozen_map


    # MARK: Accesses
    @override
    def _is_slots_key(self, key : K|str) -> bool:
        if not isinstance(key, str):
            return False
        return key in NamespaceMap.__slots__ or super()._is_slots_key(key)

    @override
    def _get_access_dict(self, key: K|str) -> dict:
        if not isinstance(key, str) or (key and key[0] != '_'):
            return self._dict
        else:
            return super()._get_access_dict(key)


    # MARK: Accesses - Write
    def _get_write_target(self, key : K|str) -> 'Namespace':
        return self

    def _Namespace__get_write_target(self, key : K|str) -> 'Namespace':
        if not isinstance(key, str) or (key and key[0] == '_'):
            return self
        else:
            return self._get_write_target(key)

    @override
    def _is_frozen_key(self, key : K|str) -> bool:
        if isinstance(key, str) and super()._is_frozen_key(key):
            return True

        if self.get('frozen_map', False) and self._get_access_dict(key) is self._dict:
            return True

        return False


    # MARK: Accesses - Read
    @override
    def get(self, key : K|str, default:Namespace.Default=Namespace.NO_DEFAULT):
        """
        Retrieve the value associated with a key.

        Args:
            key (str): The key to look up.
            default: The default value to return if the key is not found.

        Returns:
            The value associated with the key, or the default value if the key is not found.
        """
        return self._Namespace__get(key, default=default) # pyright: ignore[reportCallIssue] as this method is defined in Namespace

    def _get_read_target(self, key : K|str) -> Self|None:
        """
        Determine the target object for read operations.

        Args:
            key: The key to read.

        Returns:
            The target object for the read operation.
        """
        return self

    def _Namespace__get_read_target(self, key) -> Namespace|None:
        """
        Determine the target object for read operations in the namespace.

        Args:
            key: The key to read.

        Returns:
            The target object for the read operation.
        """
        if key and key[0] == '_':
            return self
        else:
            return self._get_read_target(key)


    # MARK: Iteration
    @override
    def __iter__(self) -> Iterable[K|str]: # pyright: ignore[reportIncompatibleMethodOverride]
        """
        Returns an iterator to the internal dictionary.

        Returns:
            An iterator over the keys of the internal dictionary.
        """
        return iter(self._dict)

    @override
    def __len__(self) -> int:
        """
        Returns the length of the internal dictionary.

        Returns:
            The number of items in the internal dictionary.
        """
        return len(self._dict)

    @override
    def keys(self) -> KeysView[K]:
        """
        Retrieve the keys of the internal dictionary.

        Returns:
            A view object containing the keys of the internal dictionary.
        """
        return self._dict.keys()

    @override
    def items(self) -> ItemsView[K,V]:
        """
        Retrieve the items of the internal dictionary.

        Returns:
            A view object containing the key-value pairs of the internal dictionary.
        """
        return self._dict.items()

    @override
    def values(self) -> ValuesView[V]:
        """
        Retrieve the values of the internal dictionary.

        Returns:
            A view object containing the values of the internal dictionary.
        """
        return self._dict.values()


    # MARK: Comparison
    @override
    def __eq__(self, other) -> bool:
        """
        Compare this object with another for equality.

        Args:
            other: The object to compare with.

        Returns:
            True if the objects are the same, False otherwise.
        """
        return self is other
        # return hash(self) == hash(other)

    @override
    def __ne__(self, other) -> bool:
        """
        Compare this object with another for inequality.

        Args:
            other: The object to compare with.

        Returns:
            True if the objects are not the same, False otherwise.
        """
        return not self.__eq__(other)
        # return hash(self) != hash(other)

    @override
    def __hash__(self) -> int:
        """
        Calculate a hash of the internal dictionary.

        Returns:
            The hash value of the internal dictionary.
        """
        return hash(frozenset(self._dict.items()))


    # MARK: Freezing - Map
    @runtime_checkable
    class FreezableMapProtocol(Protocol):
        @property
        def frozen_map(self) -> bool: ...
        @frozen_map.setter
        def frozen_map(self, val:bool) -> None: ...
        def freeze_map(self, freeze:bool=True, *, recursive:bool=False, temporary:bool=False) -> EnterExitCall|None: ...
        def unfreeze_map(self, recursive:bool=False, temporary:bool=False) -> EnterExitCall|None: ...

    def freeze_map(self, freeze=True, /, recursive=False, temporary=False) -> EnterExitCall|None:
        """
        Freeze or unfreeze the mapping.

        Args:
            freeze (bool): If True, freeze the mapping. If False, unfreeze it.
            recursive (bool): If True, apply the operation recursively to nested objects.
            temporary (bool): If True, apply the operation temporarily.

        Returns:
            An EnterExitCall object if temporary is True, otherwise None.
        """
        if temporary:
            return EnterExitCall(
                self.freeze_map, self.freeze_map,
                kwargs_enter={'freeze': freeze, 'recursive': recursive, 'temporary': False},
                kwargs_exit={'freeze': not freeze, 'recursive': recursive, 'temporary': False})

        if recursive:
            for obj in self.values():
                if isinstance(obj, self.__class__.FreezableMapProtocol) and obj.frozen_map != freeze:
                    obj.freeze_map(freeze, recursive=True, temporary=False)

        if freeze and not self.frozen_schema:
            self.freeze_schema(True, recursive=False, temporary=False)

        self.__frozen_map = freeze

    def unfreeze_map(self, recursive=False, temporary=False) -> EnterExitCall|None:
        """
        Unfreeze the mapping.

        Args:
            recursive (bool): If True, apply the operation recursively to nested objects.
            temporary (bool): If True, apply the operation temporarily.

        Returns:
            An EnterExitCall object if temporary is True, otherwise None.
        """
        return self.freeze_map(False, recursive=recursive, temporary=temporary)

    @property
    def frozen_map(self) -> bool:
        """
        Check if the mapping is frozen.

        Returns:
            True if the mapping is frozen, False otherwise.
        """
        return self.__frozen_map
    @frozen_map.setter
    def frozen_map(self, val) -> None:
        """
        Set the frozen state of the mapping.

        Args:
            val (bool): The new frozen state.
        """
        self.freeze_map(val, temporary=False)


    # MARK: Type conversion
    @override
    def asdict(self, recursive=True, private=False, protected=True, public=True) -> dict:
        """
        Convert the namespace map to a dictionary.

        Args:
            recursive (bool): If True, convert nested objects recursively.
            private (bool): If True, include private attributes.
            protected (bool): If True, include protected attributes.
            public (bool): If True, include public attributes.

        Returns:
            A dictionary representation of the namespace map.
        """
        if private or protected:
            d : dict = super().asdict(recursive=recursive, private=private, protected=protected, public=public)
        else:
            d : dict = {}

        for k, v in self._dict.items():
            if isinstance(k, str):
                if not k:
                    raise ValueError("Key cannot be an empty string")

                if k[0] == '_':
                    if '__' in k:
                        if not private:
                            continue
                    elif not protected:
                        continue

                if k[0] != '_' and not public:
                    continue

            if recursive:
                if isinstance(v, Namespace):
                    v = v.asdict(recursive=recursive, private=private, protected=protected, public=public)

                if not private and is_dataclass(v) and not isinstance(v, type):
                    v = dataclass_asdict(v)

            d[k] = v

        return d

    @override
    def merge(self, d) -> None:
        """
        Merge a dictionary into the namespace map.

        Args:
            d (dict): The dictionary to merge.
        """
        for k, v in d.items():
            self[k] = v


    # Printing
    @override
    def __repr__(self) -> str:
        """
        Generate a string representation of the namespace map.

        Returns:
            A string representation of the namespace map.
        """
        return f"<{self._Namespace__repr_name}{repr(self.asdict(recursive=False))}>"
