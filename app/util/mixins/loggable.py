# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import re
from logging import Logger
from typing import override

from . import shorten_name
from .named import NamedMixin
from .hierarchical import HierarchicalMixin

class LoggableMixin(object):
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

        setattr(self, '__log', None)

    @classmethod
    def class_short_name(cls) -> str:
        """
        Get a shortened class name for logging.

        Returns:
            str: The shortened class name.
        """
        return shorten_name(cls.__name__)


    # MARK: Support for Hierarchical/Named
    def _set_instance_parent(self, new_parent : HierarchicalMixin|None) -> None:
        """
        Set the instance parent and reset the logger.

        Args:
            new_parent: The new parent object.
        """
        super()._set_instance_parent(new_parent) # type: ignore - HierarchicalMixin provides _set_instance_parent
        setattr(self, '__log', None)

    def _set_instance_name(self, new_name : str) -> None:
        """
        Set the instance name and reset the logger.

        Args:
            new_name (str): The new name to set.
        """
        super()._set_instance_name(new_name) # type: ignore - NamedMixin provides _set_instance_name
        setattr(self, '__log', None)


    # MARK: Logging
    @property
    def log(self) -> Logger:
        """
        Returns a logger for the current object. If self.name is 'None', uses the class name.

        Returns:
            logging.Logger: The logger instance for the object.
        """
        log : Logger|None = getattr(self, '__log', None)
        if log is None:
            # TODO: Fix this once getLogger implemented
            import logging
            #from ..init import getLogger
            parent : HierarchicalMixin|None = self.instance_parent if isinstance(self, HierarchicalMixin) else None
            #log = getLogger(self.__log_name__, parent=parent)
            log = logging.getLogger(f"{parent.__class__.__name__}.{self.__log_name__}" if parent is not None else self.__log_name__)
            setattr(self, '__log', log)
        return log

    @property
    def __log_name__(self) -> str:
        """
        Get the log name for the current object.

        Returns:
            str: The log name.
        """
        return self.instance_name if isinstance(self, NamedMixin) else self.__class__.__name__

    @property
    def __log_hierarchy__(self) -> str:
        """
        Get the log hierarchy for the current object.

        Returns:
            str: The log hierarchy.
        """
        return self.instance_hierarchy if isinstance(self, HierarchicalMixin) else self.__log_name__


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