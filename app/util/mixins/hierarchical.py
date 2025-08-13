# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

from pdb import run
from typing import override, runtime_checkable, Protocol, Any

from . import shorten_name
from .named import NamedProtocol, NamedMixin


@runtime_checkable
class HierarchicalProtocol(Protocol):
    @property
    def instance_parent(self) -> Any: ...
    @property
    def instance_hierarchy(self) -> str: ...

@runtime_checkable
class HierarchicalMutableProtocol(Protocol):
    @property
    def instance_parent(self) -> Any: ...
    @property
    def instance_hierarchy(self) -> str: ...
    @instance_parent.setter
    def instance_parent(self, new_parent: Any) -> None: ...


class HierarchicalMixin:
    """
    Mixin that adds parent/child hierarchy support to a class.

    Provides instance_parent and instance_hierarchy properties, allowing objects to be organized in a tree structure.
    Used for logging, naming, and configuration inheritance in pygaindalf.
    """

    def __init__(self, *args, instance_parent: 'HierarchicalMixin | NamedMixin | None' = None, **kwargs):
        """
        Initialize the mixin and set the instance parent.

        Args:
            instance_parent: Optional parent for the instance.
            *args: Additional positional arguments for superclasses.
            **kwargs: Additional keyword arguments for superclasses.
        """
        super().__init__(*args, **kwargs)

        # Sanity check: We must come before Named
        mro = self.__class__.__mro__
        if NamedMixin in mro and mro.index(NamedMixin) < mro.index(HierarchicalMixin):
            raise TypeError(f"'HierarchicalMixin' must come *before* 'NamedMixin' in the MRO")

        self._set_instance_parent(instance_parent)

    @classmethod
    def class_short_name(cls) -> str:
        """
        Get a shortened class name for display/logging.

        Returns:
            str: The shortened class name.
        """
        return shorten_name(cls.__name__)


    # MARK: Parent
    def _set_instance_parent(self, new_parent : 'HierarchicalMixin | NamedMixin | None') -> None:
        """
        Set the instance parent.

        Args:
            new_parent (HierarchicalMixin | None): The new parent object.
        Raises:
            TypeError: If new_parent is not a HierarchicalMixin.
        """
        if new_parent is not None and not isinstance(new_parent, (HierarchicalMixin, NamedMixin)):
            raise TypeError("'new_parent' must be a class that extends 'HierarchicalMixin' or 'NamedMixin'")
        setattr(self, '__parent', new_parent)

    @property
    def instance_parent(self) -> Any:
        """
        Get the instance parent.

        Returns:
            HierarchicalMixin | None: The parent object.
        """
        return getattr(self, '__parent', None)

    @instance_parent.setter
    def instance_parent(self, new_parent : Any) -> None:
        """
        Set the instance parent.

        Args:
            new_parent: The new parent object.
        """
        self._set_instance_parent(new_parent)

    @property
    def instance_hierarchy(self) -> str:
        """
        Get the hierarchy of the instance as a string.

        Returns:
            str: The hierarchy string.
        """
        hier = self.instance_name if isinstance(self, NamedProtocol) else self.__class__.__name__

        parent = getattr(self, '__parent', None)
        if parent is None:
            pass

        elif isinstance(parent, HierarchicalProtocol):
            hier = f"{parent.instance_hierarchy}.{hier}"

        elif isinstance(parent, NamedProtocol):
            hier = f"{parent.instance_name}.{hier}"

        elif hasattr(parent, '__name__'):
            hier = f"{parent.__name__}.{hier}"

        else:
            hier = f"{parent.__class__.__name__}.{hier}"

        return hier



    # MARK: Printing
    @property
    def __repr_name(self) -> str:
        """
        Get the representation name of the instance.

        Returns:
            str: The representation name.
        """
        nm = self.instance_hierarchy
        cnm = self.__class__.__name__

        if cnm in nm:
            return nm
        else:
            return f"{cnm} {nm}"

    @override
    def __repr__(self) -> str:
        """
        Get the string representation of the instance.

        Returns:
            str: The string representation.
        """
        return f"<{self.__repr_name}>"

    @property
    def __str_name(self) -> str:
        """
        Get the string name of the instance.

        Returns:
            str: The string name.
        """
        if isinstance(self, NamedMixin):
            return self._NamedMixin__str_name # type: ignore - NamedMixin provides __str_name

        return f"{self.__class__.__name__}"

    @override
    def __str__(self) -> str:
        """
        Get the string representation of the instance.

        Returns:
            str: The string representation.
        """
        return f"<{self.__str_name}>"