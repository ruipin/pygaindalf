# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref

from abc import ABCMeta
from typing import ClassVar, Protocol, override, runtime_checkable

from ..helpers import mro
from .named import FinalNamedProtocol, NamedMixin, NamedMixinMinimal, NamedProtocol


# MARK: Type
type ParentType = HierarchicalProtocol | NamedProtocol


# MARK: Hierarchical Protocols
@runtime_checkable
class HierarchicalProtocol(Protocol):
    @property
    def instance_parent(self) -> ParentType | None: ...
    @property
    def instance_hierarchy(self) -> str: ...


@runtime_checkable
class HierarchicalMutableProtocol(HierarchicalProtocol, Protocol):
    @property
    @override
    def instance_parent(self) -> ParentType | None: ...
    @instance_parent.setter
    def instance_parent(self, new_parent: ParentType | None) -> None: ...


# MARK: Minimal Mixin for Hierarchical Classes
class HierarchicalMixinMinimal(metaclass=ABCMeta):
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        mro.ensure_mro_order(cls, HierarchicalMixinMinimal, before=(NamedMixinMinimal, NamedMixin, NamedProtocol))
        assert hasattr(cls, "instance_parent"), f"{cls.__name__} must have an 'instance_parent' property to use HierarchicalMixinMinimal"

    @property
    def instance_hierarchy(self) -> str:
        """Get the hierarchy of the instance as a string.

        Returns:
            str: The hierarchy string.

        """
        hier = None
        if isinstance(self, FinalNamedProtocol):
            hier = self.final_instance_name
        elif isinstance(self, NamedProtocol):
            hier = self.instance_name
        if hier is None:
            hier = type(self).__name__

        parent = self.instance_parent  # pyright: ignore[reportAttributeAccessIssue] as this mixin must only be used when instance_parent is accessible
        if parent is None:
            pass

        elif isinstance(parent, HierarchicalProtocol):
            hier = f"{parent.instance_hierarchy}.{hier}"

        elif (isinstance(parent, NamedProtocol) and (name := parent.instance_name)) or ((name := getattr(parent, "__name__", None)) and isinstance(name, str)):
            hier = f"{name}.{hier}"

        else:
            hier = f"{type(parent).__name__}.{hier}"

        return hier

    @property
    def __repr_name(self) -> str:
        """Get the representation name of the instance.

        Returns:
            str: The representation name.

        """
        nm = self.instance_hierarchy
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

    @override
    def __str__(self) -> str:
        """Get the string representation of the instance.

        Returns:
            str: The string representation.

        """
        if isinstance(self, NamedProtocol):
            return super().__str__()
        else:
            return f"<{type(self).__name__}>"


# MARK: Mixin for Hierarchical Classes
class HierarchicalMixin(HierarchicalMixinMinimal):
    """Mixin that adds parent/child hierarchy support to a class.

    Provides instance_parent and instance_hierarchy properties, allowing objects to be organized in a tree structure.
    Used for logging, naming, and configuration inheritance in pygaindalf.
    """

    """ Attribute name used to store the instance name
    This is used to allow base classes to customise this without needing to override the instance_name property """
    HIERARCHICAL_MIXIN_ATTRIBUTE: ClassVar[str] = "__parent"
    ALLOW_CHANGING_INSTANCE_PARENT: ClassVar[bool] = False

    def __init__(self, *args, instance_parent: ParentType | None = None, **kwargs) -> None:
        """Initialize the mixin and set the instance parent.

        Args:
            instance_parent: Optional parent for the instance.
            *args: Additional positional arguments for superclasses.
            **kwargs: Additional keyword arguments for superclasses.

        """
        super().__init__(*args, **kwargs)

        self.instance_parent = instance_parent

    # MARK: Parent
    @property
    def instance_parent(self) -> ParentType | None:
        """Get the instance parent.

        Returns:
            ParentType: The parent object.

        """
        parent = getattr(self, type(self).HIERARCHICAL_MIXIN_ATTRIBUTE, None)
        if parent is None:
            return None
        return parent() if isinstance(parent, weakref.ref) else parent

    @instance_parent.setter
    def instance_parent(self, new_parent: ParentType | None) -> None:
        """Set the instance parent.

        Args:
            new_parent: The new parent object.

        """
        if new_parent is not None and not isinstance(new_parent, (HierarchicalProtocol, NamedProtocol)):
            msg = f"Expected HierarchicalProtocol, NamedProtocol, or None, got {type(new_parent).__name__}"
            raise TypeError(msg)

        if not type(self).ALLOW_CHANGING_INSTANCE_PARENT and self.instance_parent is not None:
            msg = "Changing instance_parent is not allowed for this class."
            raise RuntimeError(msg)

        _new_parent = weakref.ref(new_parent) if new_parent is not None else None

        setattr(self, type(self).HIERARCHICAL_MIXIN_ATTRIBUTE, _new_parent)

        from .loggable import LoggableMixin

        if isinstance(self, LoggableMixin):
            self._reset_log_cache()
