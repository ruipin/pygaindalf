# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override, Protocol, Self, Any, runtime_checkable
from collections.abc import ItemsView, Iterable, KeysView, ValuesView
from dataclasses import is_dataclass, asdict as dataclass_asdict

from .. import LoggableMixin, HierarchicalMixin, NamedMixin
from ..enter_exit_call import EnterExitCall


class Namespace[T = Any]:
    """
    A flexible namespace object that can be accessed like a dictionary or using attributes.

    This class provides a dynamic container for attributes, supporting both attribute and dict-style access.
    It supports freezing (to prevent further modification), recursive merging, and can be extended with mixins
    for logging, naming, and hierarchy. Used as a base for configuration and data structures throughout pygaindalf.
    """

    # Sentinel value for parameters to indicate that no default value is provided
    class NoDefault:
        pass
    NO_DEFAULT = NoDefault()

    # Type aliases for better readability
    type Attribute  = Namespace[T] | T
    type Default    = Attribute | NoDefault
    type DictView   = dict[str, Attribute]

    # We want to hide some attributes from the dictionary
    # NOTE: We include the log/parent attributes here just in case someone decides to make this class Loggable or Hierarchical
    __slots__ = {'_Namespace__frozen_namespace', '_Namespace__frozen_schema', '_Namespace__namespace', '_NamedMixin__name', '_HierarchicalMixin__parent',
                 '_LoggableMixin__log'}


    """ Customizable class attributes """
    # Default value for attributes that do not exist return None by default. Set to NO_DEFAULT to raise KeyError instead
    NAMESPACE__DEFAULT : Default = NO_DEFAULT

    # If True, allows changing private attributes when the namespace is frozen
    NAMESPACE__FROZEN_NAMESPACE__ALLOW_PRIVATE : bool = False
    # If True, allows changing private attributes when the schema is frozen
    NAMESPACE__FROZEN_SCHEMA__ALLOW_PRIVATE : bool = False

    # If set to True, this Namespace will automatically convert dictionaries into namespaces
    NAMESPACE__STICKY : bool = False
    # If not None, this delimiter will cause STICKY=True to also split keys with this delimiter
    NAMESPACE__STICKY__DELIMITER : str|None = None


    # MARK: Constructor
    def __init__(self, *, frozen_schema=False, frozen_namespace=False, **kwargs : Attribute):
        """
        Initialize a Namespace instance.

        Args:
            frozen_schema (bool): If True, freeze the schema (no new keys allowed).
            frozen_namespace (bool): If True, freeze the namespace (no changes allowed).
            **kwargs: Initial key-value pairs to populate the namespace.
        Raises:
            TypeError: If mixin order is incorrect in the MRO.
        """
        # Sanity check: We must come before Named/Hierarchical/Loggable
        def _check_mro(mro, mixin):
            if mixin in mro and mro.index(mixin) < mro.index(Namespace):
                raise TypeError(f"'Namespace' must come *before* '{mixin}' in the MRO")
        mro = self.__class__.__mro__
        _check_mro(mro, NamedMixin)
        _check_mro(mro, HierarchicalMixin)
        _check_mro(mro, LoggableMixin)

        # Initialize basic state before calling super constructors
        self.__frozen_schema    : bool = False
        self.__frozen_namespace : bool = False

        self.__namespace : Namespace[T].DictView = {}

        # Call super-class
        super_params = {}
        if isinstance(self, NamedMixin):
            super_params['instance_name'] = kwargs.pop('instance_name', None)
        if isinstance(self, HierarchicalMixin):
            super_params['instance_parent'] = kwargs.pop('instance_parent', None)
        super().__init__(**super_params)

        # Finish initialization
        if kwargs:
            self.merge(kwargs)

        self.__frozen_schema    = frozen_schema
        self.__frozen_namespace = frozen_namespace


    # MARK: Utilities
    def _sanity_check_public_key(self, key : str, *, delete:bool=False) -> None:
        pass

    def _sanity_check_private_key(self, key : str, *, delete:bool=False) -> None:
        pass

    def _sanity_check_key(self, key : str, *, delete:bool=False) -> None:
        if not key:
            raise ValueError(f"key must be defined")

        if key[0] == '_':
            self._sanity_check_private_key(key, delete=delete)
        else:
            self._sanity_check_public_key(key, delete=delete)

    def _is_frozen_key(self, key : str) -> bool:
        if self.frozen_namespace:
            if not self.__class__.NAMESPACE__FROZEN_SCHEMA__ALLOW_PRIVATE or not key or key[0] != '_':
                return True

        if not self.frozen_schema:
            return False

        if key in self.__namespace:
            return False

        if self.__class__.NAMESPACE__FROZEN_SCHEMA__ALLOW_PRIVATE and key and key[0] == '_':
            return False

        return True

    def _is_slots_key(self, key : str) -> bool:
        return key in Namespace.__slots__

    def _get_access_dict(self, key : str) -> DictView:
        return self.__namespace


    # MARK: Adding to the namespace
    def __get_write_target(self, key : str) -> Self:
        return self

    def __set(self, key : str, value : Attribute) -> Attribute:
        """
        Add a new attribute to the namespace.

        Args:
            key (str): The key for the attribute.
            value (Any): The value to associate with the key.

        Returns:
            Any: The value that was set.

        Raises:
            TypeError: If the namespace is frozen and the key cannot be added.
            ValueError: If the key is invalid.
        """
        # Handle a __slots__ keys
        if self._is_slots_key(key):
            super().__setattr__(key, value)
            return value

        # Handle @property.setter
        if hasattr(self.__class__, key):
            attr = getattr(self.__class__, key)
            if isinstance(attr, property):
                attr.__set__(self, value)
                return value

        # Sanity checks
        if self._is_frozen_key(key):
            raise TypeError(f"{str(self)} is frozen, can't add key '{key}'")
        self._sanity_check_key(key)

        # Sticky
        if self.__class__.NAMESPACE__STICKY and not self._sticky_ignore_key(key):
            if self.__class__.NAMESPACE__STICKY__DELIMITER is not None:
                split_key = key.split(self.__class__.NAMESPACE__STICKY__DELIMITER, 1)
                if len(split_key) > 1:
                    key     = split_key[0]
                    sub_key = split_key[1]
                    self._sanity_check_key(key)

                    if key in self:
                        setattr(self[key], sub_key, value)
                        return value

                    value = self.__sticky_create_namespace(key, sub_key, value)

            if isinstance(value, dict):
                value = self.__sticky_create_namespace(key, None, value)
            elif not isinstance(value, Namespace):
                asdict = getattr(value, 'asdict', None)
                if callable(asdict):
                    d = asdict()
                    if not isinstance(d, dict):
                        raise TypeError(f"Expected a dict for sticky namespace '{key}', got {type(d).__name__}")
                    value = self.__sticky_create_namespace(key, None, d)

        # Handle custom target
        if not self.__class__.NAMESPACE__STICKY or not isinstance(value, Namespace):
            tgt : Namespace = self.__get_write_target(key)
            if tgt is not self:
                return tgt.__set(key, value)

        # Add to dictionary
        self._get_access_dict(key)[key] = value
        return value

    def __remove(self, key : str, fail:bool=True) -> None:
        """
        Remove an attribute from the namespace.

        Args:
            key (str): The key of the attribute to remove.
            fail (bool): If True, raise an exception if the key does not exist.

        Raises:
            TypeError: If the namespace is frozen and the key cannot be removed.
            ValueError: If the key is invalid.
            KeyError: If the key does not exist and fail is True.
        """
        # Handle a __slots__ key
        if self._is_slots_key(key):
            raise RuntimeError("Cannot delete __slots__ keys using __remove")

        # Sanity checks
        if self._is_frozen_key(key):
            raise TypeError(f"{repr(self)} is frozen, can't delete key '{key}'")
        self._sanity_check_key(key, delete=True)

        # Sticky
        if self.__class__.NAMESPACE__STICKY and not self._sticky_ignore_key(key):
            if self.__class__.NAMESPACE__STICKY__DELIMITER is not None:
                split_key = key.split(self.__class__.NAMESPACE__STICKY__DELIMITER, 1)
                if len(split_key) > 1:
                    self_key = split_key[0]
                    sub_key  = split_key[1]
                    self._sanity_check_key(self_key, delete=True)

                    delattr(self[self_key], sub_key)
                    return

        # Handle custom target
        tgt : Namespace = self.__get_write_target(key)
        if tgt is not self:
            tgt.__remove(key)
            return

        # Remove from dictionary
        try:
            del self._get_access_dict(key)[key]
        except KeyError:
            if fail:
                raise


    # MARK: Reading from Namespace
    def __get_read_target(self, key : str) -> Self|None:
        return self

    def __get(self, key : str, default:Default=NO_DEFAULT) -> Attribute:
        """
        Retrieve an attribute from the namespace.

        Args:
            key (str): The key of the attribute to retrieve.
            default (Any): The default value to return if the key does not exist.

        Returns:
            Any: The value associated with the key, or the default value.

        Raises:
            KeyError: If the key does not exist and no default value is provided.
        """
        # Handle a __slots__ key
        if self._is_slots_key(key):
            return super().__getattribute__(key)

        # Handle default value
        if default is Namespace.NO_DEFAULT:
            default = self.__class__.NAMESPACE__DEFAULT

        # Sticky
        if self.__class__.NAMESPACE__STICKY and not self._sticky_ignore_key(key):
            if self.__class__.NAMESPACE__STICKY__DELIMITER is not None:
                split_key = key.split(self.__class__.NAMESPACE__STICKY__DELIMITER, 1)
                if len(split_key) > 1:
                    self_key = split_key[0]
                    sub_key = split_key[1]
                    self._sanity_check_key(self_key, delete=True)

                    if self_key not in self:
                        if isinstance(default, Namespace.NoDefault):
                            raise KeyError()
                        else:
                            return default

                    return getattr(self[self_key], sub_key)

        # Handle custom target
        tgt = self.__get_read_target(key)

        if tgt is None:
            if isinstance(default, Namespace.NoDefault):
                raise KeyError(f"Key '{key}' does not exist in {repr(self)}")
            return default

        if tgt is not self:
            return tgt.__get(key, default=default)

        # Get an entry from the internal dictionary
        d = self._get_access_dict(key)
        if isinstance(default, Namespace.NoDefault):
            return d[key]
        else:
            return d.get(key, default)


    # MARK: Sticky
    @classmethod
    def _sticky_construct_class(cls) -> type:
        """
        Get the class to use for constructing sticky namespaces.

        Returns:
            type: The class to use for sticky namespaces.
        """
        return cls

    def __sticky_construct_namespace(self, key : str) -> Self:
        """
        Construct a sticky namespace.

        Args:
            key (str): The key for the sticky namespace.

        Returns:
            Namespace: The constructed sticky namespace.
        """
        super_params = {}
        if isinstance(self, HierarchicalMixin):
            super_params['instance_parent'] = self
        if isinstance(self, NamedMixin):
            super_params['instance_name'] = key
        super_params['frozen_schema'] = self.frozen_schema

        return self._sticky_construct_class()(**super_params)

    def __sticky_create_namespace(self, key : str, sub_key : str|None, value : Attribute|DictView) -> Self:
        """
        Create a sticky namespace.

        Args:
            key (str): The key for the sticky namespace.
            sub_key (str): The sub-key for the sticky namespace.
            value (Any): The value to associate with the sub-key.

        Returns:
            Namespace: The created sticky namespace.
        """
        inst = self.__sticky_construct_namespace(key)

        if sub_key is None:
            if not isinstance(value, dict):
                raise TypeError(f"Expected a dict for sticky namespace '{key}', got {type(value).__name__}")
            inst.merge(value)
        else:
            setattr(inst, sub_key, value)

        return inst

    def _sticky_ignore_key(self, key : str) -> bool:
        """
        Determine whether to ignore a key for sticky processing.

        Args:
            key (str): The key to check.

        Returns:
            bool: True if the key should be ignored, False otherwise.
        """
        return False


    # MARK: Dictionary Magic Methods
    def __getitem__(self, key : str) -> Attribute:
        """
        Get an attribute using dictionary syntax obj[key].

        Args:
            key (str): The key of the attribute to retrieve.

        Returns:
            Any: The value associated with the key.

        Raises:
            KeyError: If the key does not exist.
        """
        if self._is_slots_key(key):
            raise KeyError
        return self.__get(key)

    def __setitem__(self, key : str, value : Attribute) -> None:
        """
        Modify an attribute using dictionary syntax obj[key] = value.

        Args:
            key (str): The key of the attribute to modify.
            value (Any): The new value to associate with the key.

        Raises:
            KeyError: If the key is invalid.
        """
        if self._is_slots_key(key):
            raise KeyError
        self.__set(key, value)

    def __delitem__(self, key : str) -> None:
        """
        Delete an attribute using dictionary syntax.

        Args:
            key (str): The key of the attribute to delete.

        Raises:
            KeyError: If the key is invalid.
        """
        if self._is_slots_key(key):
            raise KeyError
        self.__remove(key)

    def __contains__(self, m : str) -> bool:
        """
        Check if a key exists in the namespace.

        Args:
            m (str): The key to check.

        Returns:
            bool: True if the key exists, False otherwise.
        """
        try:
            self.__getitem__(m)
            return True
        except KeyError:
            return False


    # MARK: Attribute Magic Methods
    def __getattr__(self, key : str) -> Attribute:
        """
        Get an attribute, redirected to the internal dictionary.

        Args:
            key (str): The key of the attribute to retrieve.

        Returns:
            Any: The value associated with the key.

        Raises:
            AttributeError: If the attribute does not exist.
        """
        try:
            return self.__get(key)
        except KeyError:
            raise AttributeError(f"Attribute '{key}' does not exist")

    @override
    def __setattr__(self, key : str, value : Attribute) -> None:
        """
        Set an attribute, redirected to the internal dictionary.

        Args:
            key (str): The key of the attribute to set.
            value (Any): The value to associate with the key.
        """
        self.__set(key, value)

    @override
    def __delattr__(self, key : str) -> None:
        """
        Delete an attribute using attribute syntax.

        Args:
            key (str): The key of the attribute to delete.
        """
        self.__remove(key)


    # Iteration
    def __iter__(self) -> Iterable[str]:
        """
        Returns an iterator to the internal dictionary.

        Returns:
            Iterator: An iterator over the keys in the namespace.
        """
        return iter(self.__namespace)

    def __len__(self) -> int:
        """
        Returns the length of the internal dictionary.

        Returns:
            int: The number of keys in the namespace.
        """
        return len(self.__namespace)

    def __keys(self) -> KeysView[str]:
        """
        Get the keys of the internal dictionary.

        Returns:
            KeysView: The keys of the namespace.
        """
        return self.__namespace.keys()

    def __items(self) -> ItemsView[str, Attribute]:
        """
        Get the items of the internal dictionary.

        Returns:
            ItemsView: The items of the namespace.
        """
        return self.__namespace.items()

    def __values(self) -> ValuesView[Attribute]:
        """
        Get the values of the internal dictionary.

        Returns:
            ValuesView: The values of the namespace.
        """
        return self.__namespace.values()


    # MARK: Comparison
    @override
    def __eq__(self, other : object) -> bool:
        """
        Check if two namespaces are equal.

        Args:
            other (Namespace): The other namespace to compare.

        Returns:
            bool: True if the namespaces are equal, False otherwise.
        """
        return self is other
        # return hash(self) == hash(other)

    @override
    def __ne__(self, other : object) -> bool:
        """
        Check if two namespaces are not equal.

        Args:
            other (Namespace): The other namespace to compare.

        Returns:
            bool: True if the namespaces are not equal, False otherwise.
        """
        return not self.__eq__(other)
        # return hash(self) != hash(other)

    @override
    def __hash__(self) -> int:
        """
        Get the hash of the namespace.

        Returns:
            int: The hash of the namespace.
        """
        # The object id is guaranteed to be unique for the lifetime of the object
        return id(self)


    # MARK: Freezing - Schema
    @runtime_checkable
    class FreezableSchemaProtocol(Protocol):
        @property
        def frozen_schema(self) -> bool: ...
        @frozen_schema.setter
        def frozen_schema(self, val:bool) -> None: ...
        def freeze_schema(self, freeze:bool=True, *, recursive:bool=False, temporary:bool=False) -> EnterExitCall|None: ...
        def unfreeze_schema(self, recursive:bool=False, temporary:bool=False) -> EnterExitCall|None: ...

    def freeze_schema(self, freeze:bool=True, *, recursive:bool=False, temporary:bool=False) -> EnterExitCall|None:
        """
        Freeze the schema of the namespace.

        Args:
            freeze (bool): If True, freeze the schema.
            recursive (bool): If True, apply freezing recursively to nested namespaces.
            temporary (bool): If True, apply freezing temporarily.

        Returns:
            EnterExitCall: A context manager for temporary freezing.
        """
        if temporary:
            return EnterExitCall(
                self.freeze_schema, self.freeze_schema,
                kwargs_enter={'freeze': freeze, 'recursive': recursive, 'temporary': False},
                kwargs_exit={'freeze': not freeze, 'recursive': recursive, 'temporary': False})

        if recursive:
            for obj in self.__values():
                if isinstance(obj, self.__class__.FreezableSchemaProtocol) and obj.frozen_schema != freeze:
                    obj.freeze_schema(freeze=freeze, recursive=recursive, temporary=temporary)

        self.__frozen_schema = freeze

    def unfreeze_schema(self, recursive:bool=False, temporary:bool=False) -> EnterExitCall|None:
        """
        Unfreeze the schema of the namespace.

        Args:
            recursive (bool): If True, apply unfreezing recursively to nested namespaces.
            temporary (bool): If True, apply unfreezing temporarily.

        Returns:
            EnterExitCall: A context manager for temporary unfreezing.
        """
        return self.freeze_schema(False, recursive=recursive, temporary=temporary)

    @property
    def frozen_schema(self) -> bool:
        """
        Get the frozen state of the schema.

        Returns:
            bool: True if the schema is frozen, False otherwise.
        """
        return self.__frozen_schema
    @frozen_schema.setter
    def frozen_schema(self, val : bool) -> None:
        """
        Set the frozen state of the schema.

        Args:
            val (bool): The new frozen state.
        """
        self.freeze_schema(val, temporary=False)


    # MARK: Freezing - Namespace
    @runtime_checkable
    class FreezableNamespaceProtocol(Protocol):
        @property
        def frozen_namespace(self) -> bool: ...
        @frozen_namespace.setter
        def frozen_namespace(self, val:bool) -> None: ...
        def freeze_namespace(self, freeze:bool=True, *, recursive:bool=False, temporary:bool=False) -> EnterExitCall|None: ...
        def unfreeze_namespace(self, recursive:bool=False, temporary:bool=False) -> EnterExitCall|None: ...

    def freeze_namespace(self, freeze:bool=True, *, recursive:bool=False, temporary:bool=False) -> EnterExitCall|None:
        """
        Freeze the namespace.

        Args:
            freeze (bool): If True, freeze the namespace.
            recursive (bool): If True, apply freezing recursively to nested namespaces.
            temporary (bool): If True, apply freezing temporarily.

        Returns:
            EnterExitCall: A context manager for temporary freezing.
        """
        if temporary:
            return EnterExitCall(
                self.freeze_namespace, self.freeze_namespace,
                kwargs_enter={'freeze': freeze, 'recursive': recursive, 'temporary': False},
                kwargs_exit={'freeze': not freeze, 'recursive': recursive, 'temporary': False})

        if recursive:
            for obj in self.__values():
                if isinstance(obj, self.__class__.FreezableNamespaceProtocol) and obj.frozen_namespace != freeze:
                    obj.freeze_namespace(freeze=freeze, recursive=True, temporary=False)

        self.__frozen_namespace = freeze

    def unfreeze_namespace(self, recursive:bool=False, temporary:bool=False) -> EnterExitCall|None:
        """
        Unfreeze the namespace.

        Args:
            recursive (bool): If True, apply unfreezing recursively to nested namespaces.
            temporary (bool): If True, apply unfreezing temporarily.

        Returns:
            EnterExitCall: A context manager for temporary unfreezing.
        """
        return self.freeze_schema(False, recursive=recursive, temporary=temporary)

    @property
    def frozen_namespace(self) -> bool:
        """
        Get the frozen state of the namespace.

        Returns:
            bool: True if the namespace is frozen, False otherwise.
        """
        return self.__frozen_namespace
    @frozen_namespace.setter
    def frozen_namespace(self, val : bool) -> None:
        """
        Set the frozen state of the namespace.

        Args:
            val (bool): The new frozen state.
        """
        self.freeze_namespace(val, temporary=False)


    # MARK: Type conversion
    def asdict(self, recursive:bool=True, private:bool=False, protected:bool=True, public:bool=True) -> DictView:
        """
        Convert the namespace to a dictionary.

        Args:
            recursive (bool): If True, convert nested namespaces recursively.
            private (bool): If True, include private attributes.
            protected (bool): If True, include protected attributes.
            public (bool): If True, include public attributes.

        Returns:
            dict: The namespace as a dictionary.
        """
        d = {}
        for k, v in self.__namespace.items():
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

    def merge(self, d : DictView) -> None:
        """
        Merge a dictionary into the namespace.

        Args:
            d (dict): The dictionary to merge.
        """
        for k, v in d.items():
            self[k] = v


    # MARK: Printing
    @property
    def __repr_name(self) -> str:
        """
        Get the name to use in the representation.

        Returns:
            str: The name to use in the representation.
        """
        if isinstance(self, LoggableMixin):
            return self._LoggableMixin__repr_name # pyright: ignore[reportReturnType] since LoggableMixing provides __repr_name
        if isinstance(self, HierarchicalMixin):
            return self._HierarchicalMixin__repr_name # pyright: ignore[reportReturnType] since HierarchicalMixin provides __repr_name
        return self.__class__.__name__

    @override
    def __repr__(self) -> str:
        """
        Get the string representation of the namespace.

        Returns:
            str: The string representation of the namespace.
        """
        return f"<{self.__repr_name}{repr(self.asdict(recursive=False))}>"
