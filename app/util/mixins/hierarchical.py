# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

from pdb import run
from typing import override, runtime_checkable, Protocol, ClassVar
from abc import abstractmethod, ABCMeta

from ..helpers import mro

from .named import NamedProtocol, NamedMixin, NamedMixinMinimal


# MARK: Hierarchical Protocols
@runtime_checkable
class HierarchicalProtocol(Protocol):
    @property
    def instance_parent(self) -> 'HierarchicalProtocol | NamedProtocol | None': ...
    @property
    def instance_hierarchy(self) -> str: ...

@runtime_checkable
class HierarchicalMutableProtocol(HierarchicalProtocol, Protocol):
    @property
    @override
    def instance_parent(self) -> HierarchicalProtocol | NamedProtocol | None: ...
    @instance_parent.setter
    def instance_parent(self, new_parent: HierarchicalProtocol | NamedProtocol | None) -> None: ...


# MARK: Minimal Mixin for Hierarchical Classes
class HierarchicalMixinMinimal(metaclass=ABCMeta):
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        mro.ensure_mro_order(cls, HierarchicalMixinMinimal, before=(NamedMixinMinimal, NamedMixin, NamedProtocol))

    @property
    @abstractmethod
    def instance_parent(self) -> 'HierarchicalProtocol | NamedProtocol | None':
        raise NotImplementedError("Subclasses must implement instance_parent")

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

    @override
    def __str__(self) -> str:
        """
        Get the string representation of the instance.

        Returns:
            str: The string representation.
        """
        if isinstance(self, NamedProtocol):
            return super().__str__()
        else:
            return f"<{self.__class__.__name__}>"


# MARK: Mixin for Hierarchical Classes
class HierarchicalMixin(HierarchicalMixinMinimal):
    """
    Mixin that adds parent/child hierarchy support to a class.

    Provides instance_parent and instance_hierarchy properties, allowing objects to be organized in a tree structure.
    Used for logging, naming, and configuration inheritance in pygaindalf.
    """

    """ Attribute name used to store the instance name
    This is used to allow base classes to customise this without needing to override the instance_name property """
    HIERARCHICAL_MIXIN_ATTRIBUTE : ClassVar[str] = '__parent'

    def __init__(self, *args, instance_parent: HierarchicalProtocol | NamedProtocol | None = None, **kwargs):
        """
        Initialize the mixin and set the instance parent.

        Args:
            instance_parent: Optional parent for the instance.
            *args: Additional positional arguments for superclasses.
            **kwargs: Additional keyword arguments for superclasses.
        """
        super().__init__(*args, **kwargs)

        self.instance_parent = instance_parent


    # MARK: Parent
    @property
    @override
    def instance_parent(self) -> HierarchicalProtocol | NamedProtocol | None:
        """
        Get the instance parent.

        Returns:
            HierarchicalProtocol | NamedProtocol | None: The parent object.
        """
        return getattr(self, self.__class__.HIERARCHICAL_MIXIN_ATTRIBUTE, None)

    @instance_parent.setter
    def instance_parent(self, new_parent : HierarchicalProtocol | NamedProtocol | None) -> None:
        """
        Set the instance parent.

        Args:
            new_parent: The new parent object.
        """
        if new_parent is not None and not isinstance(new_parent, (HierarchicalProtocol, NamedProtocol)):
            raise TypeError(f"Expected HierarchicalProtocol, NamedProtocol, or None, got {type(new_parent).__name__}")

        setattr(self, self.__class__.HIERARCHICAL_MIXIN_ATTRIBUTE, new_parent)

        from .loggable import LoggableMixin
        if isinstance(self, LoggableMixin):
            self._reset_log_cache()