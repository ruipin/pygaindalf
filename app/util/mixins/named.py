# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

from . import shorten_name
from typing import override


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
        self.__name = instance_name

    @classmethod
    def class_short_name(cls) -> str:
        """
        Get a shortened class name for display/logging.

        Returns:
            str: The shortened class name.
        """
        return shorten_name(cls.__name__)


    # MARK: Logging
    def _set_instance_name(self, new_name : str) -> None:
        """
        Set the instance name.

        Args:
            new_name (str): The new name to set.
        """
        self.__name = new_name

    @property
    def instance_name(self) -> str:
        """
        Get the instance name, or class name if not set.

        Returns:
            str: The instance name.
        """
        return self.__name or self.__class__.__name__

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
            return f"{self.__class__.class_short_name()} {nm}"

    @override
    def __str__(self) -> str:
        """
        Get the string representation of the instance.

        Returns:
            str: The string representation.
        """
        return f"<{self.__str_name}>"