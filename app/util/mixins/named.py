# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Protocol, runtime_checkable

from . import shorten_name
from typing import override, ClassVar
from abc import ABCMeta, abstractmethod

from ..helpers.classinstancemethod import classinstancemethod


# MARK: Protocols
@runtime_checkable
class NamedProtocol(Protocol):
    @property
    def instance_name(self) -> str: ...
    @property
    def instance_short_name(self) -> str: ...

@runtime_checkable
class NamedMutableProtocol(NamedProtocol, Protocol):
    @property
    @override
    def instance_name(self) -> str: ...
    @instance_name.setter
    def instance_name(self, new_name: str) -> None: ...
    def is_instance_name_default(self) -> bool: ...


# MARK: Minimal Mixin for Named Classes
class NamedMixinMinimal(metaclass=ABCMeta):
    @property
    @abstractmethod
    def instance_name(self) -> str:
        raise NotImplementedError("Subclasses must implement instance_name")

    @property
    def instance_short_name(self) -> str:
        """
        Get a shortened version of the instance name.

        Returns:
            str: The shortened instance name.
        """
        return shorten_name(self.instance_name)

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

    def is_instance_name_default(self) -> bool:
        """
        Check if the instance name is the default name.

        Returns:
            bool: True if the instance name is the default, False otherwise.
        """
        return self.instance_name == self.get_default_name()

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


# MARK: Mixin for Named Classes
class NamedMixin(NamedMixinMinimal):
    """
    Mixin that adds a name to a class instance.

    Provides instance_name and related properties for identification, logging, and display purposes.
    Used for configuration, logging, and user-facing objects in pygaindalf.
    """

    """ Attribute name used to store the instance name
    This is used to allow base classes to customise this without needing to override the instance_name property """
    NAMED_MIXIN_ATTRIBUTE : ClassVar[str] = '__name'


    def __init__(self, *args, instance_name:str|None=None, **kwargs):
        """
        Initialize the mixin and set the instance name.

        Args:
            instance_name (Optional[str]): Optional name for the instance.
            *args: Additional positional arguments for superclasses.
            **kwargs: Additional keyword arguments for superclasses.
        """
        super().__init__(*args, **kwargs)

        self.instance_name = instance_name


    @property
    @override
    def instance_name(self) -> str:
        """
        Get the instance name, or class name if not set.

        Returns:
            str: The instance name.
        """
        name = getattr(self, self.__class__.NAMED_MIXIN_ATTRIBUTE, None)
        return name if name is not None else self.get_default_name()

    @instance_name.setter
    def instance_name(self, new_name : str | None) -> None:
        """
        Set the instance name.

        Args:
            new_name (str): The new name to set.
        """
        setattr(self, self.__class__.NAMED_MIXIN_ATTRIBUTE, new_name)

        from .loggable import LoggableMixin
        if isinstance(self, LoggableMixin):
            self._reset_log_cache()


    def __set_name__(self, owner : type, name : str):
        """
        Set the instance name based on the attribute name and owner
        """
        if self.instance_name is None:
            from . import HierarchicalProtocol, NamedProtocol
            if isinstance(self, HierarchicalProtocol):
                if isinstance(owner, NamedProtocol):
                    owner_name = owner.instance_name
                elif hasattr(owner, '__name__'):
                    owner_name = owner.__name__
                else:
                    owner_name = owner.__class__.__name__
                self.instance_name = f"{owner_name}.{name}"
            else:
                self.instance_name = name