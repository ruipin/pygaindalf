# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override

from . import shorten_name
from .named import NamedMixin

class HierarchicalMixin:
    """
    Mixin that adds parent/child hierarchy support to a class.

    Provides instance_parent and instance_hierarchy properties, allowing objects to be organized in a tree structure.
    Used for logging, naming, and configuration inheritance in pygaindalf.
    """

    # TODO: Remove once Python 3.14 is the minimum supported version as it does not require quoting the current class name in type hint
    type HierarchicalMixin = 'HierarchicalMixin'

    def __init__(self, *args, instance_parent: HierarchicalMixin|None = None, **kwargs):
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

        self.__parent : HierarchicalMixin|None = instance_parent

    @classmethod
    def class_short_name(cls) -> str:
        """
        Get a shortened class name for display/logging.

        Returns:
            str: The shortened class name.
        """
        return shorten_name(cls.__name__)


    # MARK: Parent
    def _set_instance_parent(self, new_parent : HierarchicalMixin|None) -> None:
        """
        Set the instance parent.

        Args:
            new_parent (HierarchicalMixin | None): The new parent object.
        Raises:
            TypeError: If new_parent is not a HierarchicalMixin.
        """
        if new_parent is not None and not isinstance(new_parent, HierarchicalMixin):
            raise TypeError("'new_parent' must be a class that extends 'HierarchicalMixin'")
        self.__parent = new_parent

    @property
    def instance_parent(self) -> HierarchicalMixin|None:
        """
        Get the instance parent.

        Returns:
            HierarchicalMixin | None: The parent object.
        """
        return self.__parent

    @instance_parent.setter
    def instance_parent(self, new_parent : HierarchicalMixin|None) -> None:
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
        hier = self.instance_name if isinstance(self, NamedMixin) else self.__class__.__name__
        if self.__parent is None:
            return hier

        return f"{self.__parent.instance_hierarchy}.{hier}"


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