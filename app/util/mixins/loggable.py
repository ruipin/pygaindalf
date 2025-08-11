# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override, Any

from .named import NamedMixin
from .hierarchical import HierarchicalMixin, HierarchicalProtocol

from ..helpers.classinstanceproperty import classinstanceproperty
from ..helpers.classinstancemethod import classinstancemethod
from ..logging import Logger, getLogger, LoggableProtocol


class LoggableMixin:
    """
    Mixin that adds a logger to a class.

    Provides a .log property for hierarchical logging, and integrates with instance naming and hierarchy if present.
    Used throughout pygaindalf for consistent, contextual logging.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the mixin and set up the logger.

        Args:
            *args: Additional positional arguments for superclasses.
            **kwargs: Additional keyword arguments for superclasses.
        """
        super().__init__(*args, **kwargs)

        # Sanity check: We must come before Named
        mro = self.__class__.__mro__
        if NamedMixin in mro and mro.index(NamedMixin) < mro.index(LoggableMixin):
            raise TypeError(f"'LoggableMixin' must come *before* 'NamedMixin' in the MRO")
        if HierarchicalMixin in mro and mro.index(HierarchicalMixin) < mro.index(LoggableMixin):
            raise TypeError(f"'LoggableMixin' must come *before* 'NamedMixin' in the MRO")

        self._reset_log_cache()


    # MARK: Named/Hierarchical integration
    def _set_instance_name(self, new_name : str) -> None:
        """
        Set the instance name for logging and identification.

        Args:
            name (str): The name to set for the instance.
        """
        if isinstance(self, NamedMixin):
            super()._set_instance_name(new_name) # pyright: ignore [reportAttributeAccessIssue] - NamedMixin provides _set_instance_name
            self._reset_log_cache()

    def _set_instance_parent(self, new_parent: HierarchicalMixin|None) -> None:
        """
        Set the instance parent for hierarchical logging and identification.

        Args:
            new_parent (HierarchicalMixin|None): The new parent to set for the instance.
        """
        if isinstance(self, HierarchicalMixin):
            super()._set_instance_parent(new_parent) # pyright: ignore [reportAttributeAccessIssue] - HierarchicalMixin provides _set_instance_parent
            self._reset_log_cache()


    # MARK: Logging
    @classinstanceproperty
    def log(self) -> Logger:
        """
        Returns a logger for the current object. If self.name is 'None', uses the class name.

        Returns:
            logging.Logger: The logger instance for the object.
        """
        log : Logger|None = getattr(self, '__log', None)
        if log is None:
            parent = getattr(self, 'instance_parent', None)
            if not isinstance(parent, LoggableProtocol):
                parent = None
            log = getLogger(self.__log_name__, parent=parent)
            setattr(self, '__log', log)
        return log

    @classinstancemethod
    def _reset_log_cache(self) -> None:
        setattr(self, '__log', None)

    @classinstanceproperty
    def __default_log_name__(self) -> str:
        """
        Get the default log name for the current object.

        Returns:
            str: The default log name.
        """
        name = getattr(self, '__name__', None)
        if name is None:
            name = getattr(self.__class__, '__name__', None)
        if name is None:
            raise ValueError("Could not determine default name")
        if isinstance(self, type):
            name = f"T({name})"
        return name

    @classinstanceproperty
    def __log_name__(self) -> str:
        """
        Get the log name for the current object.

        Returns:
            str: The log name.
        """
        instance_name = getattr(self, 'instance_name', None)
        if isinstance(instance_name, str):
            return instance_name
        return self.__default_log_name__

    @classinstanceproperty
    def __log_hierarchy__(self) -> str:
        """
        Get the log hierarchy for the current object.

        Returns:
            str: The log hierarchy.
        """
        return self.instance_hierarchy if isinstance(self, HierarchicalProtocol) else self.__log_name__


    # MARK: Printing
    @property
    def __repr_name(self) -> str:
        """
        Get the representation name for the current object.

        Returns:
            str: The representation name.
        """
        nm = self.__log_hierarchy__
        cnm = self.__class__.__name__

        if cnm in nm:
            return nm
        else:
            return f"{cnm}:{nm}"

    @override
    def __repr__(self) -> str:
        """
        Get the string representation of the current object.

        Returns:
            str: The string representation.
        """
        return f"<{self.__repr_name}>"

    @property
    def __str_name(self) -> str:
        """
        Get the string name for the current object.

        Returns:
            str: The string name.
        """
        if isinstance(self, NamedMixin):
            return self._NamedMixin__str_name # type: ignore - NamedMixin provides __str_name

        return f"{self.__class__.__name__}"

    @override
    def __str__(self) -> str:
        """
        Get the string representation of the current object.

        Returns:
            str: The string representation.
        """
        return f"<{self.__str_name}>"