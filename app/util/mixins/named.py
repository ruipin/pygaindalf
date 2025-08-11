# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Protocol, runtime_checkable

from . import shorten_name
from typing import override

from ..helpers.classinstancemethod import classinstancemethod


@runtime_checkable
class NamedProtocol(Protocol):
    @property
    def instance_name(self) -> str: ...
    @property
    def instance_short_name(self) -> str: ...

@runtime_checkable
class NamedMutableProtocol(Protocol):
    @property
    def instance_name(self) -> str: ...
    @property
    def instance_short_name(self) -> str: ...
    @instance_name.setter
    def instance_name(self, new_name: str) -> None: ...



class NamedMixin:
    """
    Mixin that adds a name to a class instance.

    Provides instance_name and related properties for identification, logging, and display purposes.
    Used for configuration, logging, and user-facing objects in pygaindalf.
    """

    def __init__(self, *args, instance_name:str|None=None, **kwargs):
        """
        Initialize the mixin and set the instance name.

        Args:
            instance_name (Optional[str]): Optional name for the instance.
            *args: Additional positional arguments for superclasses.
            **kwargs: Additional keyword arguments for superclasses.
        """
        super().__init__(*args, **kwargs)
        self._set_instance_name(instance_name)


    @classinstancemethod
    def get_default_name(self) -> str:
        """
        Get the default name for logging.

        Returns:
            str: The default name.
        """
        name = getattr(self, '__name__', None)
        if name is None:
            name = getattr(self.__class__, '__name__', None)
        if name is None:
            raise ValueError("Could not determine default name")
        return name

    @classinstancemethod
    def get_default_short_name(self) -> str:
        """
        Get a shortened default name for logging.

        Returns:
            str: The shortened default name.
        """
        return shorten_name(self.get_default_name())


    # MARK: Logging
    def _set_instance_name(self, new_name : str | None) -> None:
        """
        Set the instance name.

        Args:
            new_name (str | None): The new name to set.
        """
        setattr(self, '__name', new_name)

    @property
    def instance_name(self) -> str:
        """
        Get the instance name, or class name if not set.

        Returns:
            str: The instance name.
        """
        name = getattr(self, '__name', None)
        return name if name is not None else self.get_default_name()

    @instance_name.setter
    def instance_name(self, new_name : str) -> None:
        """
        Set the instance name.

        Args:
            new_name (str): The new name to set.
        """
        self._set_instance_name(new_name)

    @property
    def instance_short_name(self) -> str:
        """
        Get a shortened version of the instance name.

        Returns:
            str: The shortened instance name.
        """
        return shorten_name(self.instance_name)


    def __set_name__(self, owner : type, name : str):
        """
        Set the instance name based on the attribute name and owner
        """
        if self.instance_name is None:
            from . import HierarchicalMixin
            if isinstance(self, HierarchicalMixin):
                if isinstance(owner, NamedMixin):
                    owner_name = owner.instance_name
                elif hasattr(owner, '__name__'):
                    owner_name = owner.__name__
                else:
                    owner_name = owner.__class__.__name__
                self.instance_name = f"{owner_name}.{name}"
            else:
                self.instance_name = name


    # MARK: Printing
    @property
    def __repr_name(self) -> str:
        """
        Get the name to use in __repr__ output.

        Returns:
            str: The name for __repr__.
        """
        nm  = self.instance_name
        cnm = self.__class__.__name__

        if cnm in nm:
            return nm
        else:
            return f"{cnm}:{nm}"

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
        Get the string name for the instance.

        Returns:
            str: The string name.
        """
        nm = self.instance_name
        cnm = self.__class__.__name__

        if nm == cnm:
            return nm
        else:
            return f"{self.__class__.get_default_short_name()} {nm}"

    @override
    def __str__(self) -> str:
        """
        Get the string representation of the instance.

        Returns:
            str: The string representation.
        """
        return f"<{self.__str_name}>"