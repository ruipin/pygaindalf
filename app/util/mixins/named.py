# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import re

from abc import ABCMeta
from typing import ClassVar, Protocol, override, runtime_checkable

from ...util.helpers import type_hints


# MARK: shorten_name
def shorten_name(name: str) -> str:
    # Assume camelcase
    res = re.sub("[^A-Z0-9]", "", name)
    if res:
        return res

    # Otherwise, do nothing
    return name


# MARK: Protocols
@runtime_checkable
class NamedProtocol(Protocol):
    @property
    def instance_name(self) -> str | None: ...


@runtime_checkable
class FinalNamedProtocol(NamedProtocol, Protocol):
    @property
    def final_instance_name(self) -> str: ...


@runtime_checkable
class NamedMutableProtocol(NamedProtocol, Protocol):
    @property
    @override
    def instance_name(self) -> str | None: ...
    @instance_name.setter
    def instance_name(self, new_name: str | None) -> None: ...


# MARK: Minimal Mixin for Named Classes
class NamedMixinMinimal(metaclass=ABCMeta):
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        assert hasattr(cls, "instance_name") or type_hints.get_type_hint(cls, "instance_name"), (
            f"{cls.__name__} must have an 'instance_name' property to use NamedMixinMinimal"
        )

    @property
    def final_instance_name(self) -> str:
        if (name := self.instance_name) is None:  # pyright: ignore[reportAttributeAccessIssue] as this mixin must only be used when instance_name is accessible
            name = self.get_default_name()
        return name

    @property
    def instance_short_name(self) -> str | None:
        """Get a shortened version of the instance name.

        Returns:
            str: The shortened instance name.

        """
        name = self.instance_name  # pyright: ignore[reportAttributeAccessIssue] as this mixin must only be used when instance_name is accessible
        return shorten_name(name) if name is not None else None

    @property
    def final_instance_short_name(self) -> str:
        return shorten_name(self.final_instance_name)

    @classmethod
    def get_default_name(cls) -> str:
        """Get the default name for logging.

        Returns:
            str: The default name.

        """
        name = getattr(cls, "__name__", None)
        if name is None:
            msg = "Could not determine default name"
            raise ValueError(msg)
        return name

    @property
    def __repr_name(self) -> str:
        """Get the name to use in __repr__ output.

        Returns:
            str: The name for __repr__.

        """
        nm = self.final_instance_name
        cnm = type(self).__name__

        if cnm in nm:
            return nm
        else:
            return f"{cnm} {nm}"

    @override
    def __repr__(self) -> str:
        """Get the string representation of the instance.

        Returns:
            str: The string representation.

        """
        return f"<{self.__repr_name}>"

    @property
    def __str_name(self) -> str:
        """Get the string name for the instance.

        Returns:
            str: The string name.

        """
        nm = self.final_instance_name
        cnm = type(self).__name__

        if cnm in nm:
            return nm
        else:
            return f"{shorten_name(type(self).__name__)} {nm}"

    @override
    def __str__(self) -> str:
        """Get the string representation of the instance.

        Returns:
            str: The string representation.

        """
        return f"<{self.__str_name}>"


# MARK: Mixin for Named Classes
class NamedMixin(NamedMixinMinimal):
    """Mixin that adds a name to a class instance.

    Provides instance_name and related properties for identification, logging, and display purposes.
    Used for configuration, logging, and user-facing objects in pygaindalf.
    """

    """ Attribute name used to store the instance name
    This is used to allow base classes to customise this without needing to override the instance_name property """
    NAMED_MIXIN_ATTRIBUTE: ClassVar[str] = "__name"

    def __init__(self, *args, instance_name: str | None = None, **kwargs) -> None:
        """Initialize the mixin and set the instance name.

        Args:
            instance_name (Optional[str]): Optional name for the instance.
            *args: Additional positional arguments for superclasses.
            **kwargs: Additional keyword arguments for superclasses.

        """
        super().__init__(*args, **kwargs)

        self.instance_name = instance_name

    @property
    def instance_name(self) -> str | None:
        """Get the instance name, or class name if not set.

        Returns:
            str: The instance name.

        """
        return getattr(self, type(self).NAMED_MIXIN_ATTRIBUTE, None)

    @instance_name.setter
    def instance_name(self, new_name: str | None) -> None:
        """Set the instance name.

        Args:
            new_name (str): The new name to set.

        """
        setattr(self, type(self).NAMED_MIXIN_ATTRIBUTE, new_name)

        from .loggable import LoggableMixin

        if isinstance(self, LoggableMixin):
            self._reset_log_cache()

    def __set_name__(self, owner: type, name: str) -> None:
        """Set the instance name based on the attribute name and owner."""
        if self.instance_name is None:
            from . import HierarchicalProtocol, NamedProtocol

            if isinstance(self, HierarchicalProtocol):
                if isinstance(owner, NamedProtocol):
                    owner_name = owner.instance_name
                elif hasattr(owner, "__name__"):
                    owner_name = owner.__name__
                else:
                    owner_name = type(owner).__name__
                self.instance_name = f"{owner_name}.{name}"
            else:
                self.instance_name = name
