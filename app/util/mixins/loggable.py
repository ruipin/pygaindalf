# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override, Any

from .hierarchical import HierarchicalMixin, HierarchicalProtocol, HierarchicalMixinMinimal
from .named import NamedProtocol, NamedMixin, NamedMixinMinimal

from ..helpers.classinstanceproperty import classinstanceproperty
from ..helpers.classinstancemethod import classinstancemethod
from ..helpers import mro
from ..logging import Logger, getLogger, LoggableProtocol


class LoggableMixin:
    """
    Mixin that adds a logger to a class.

    Provides a .log property for hierarchical logging, and integrates with instance naming and hierarchy if present.
    Used throughout pygaindalf for consistent, contextual logging.
    """

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        mro.ensure_mro_order(cls, LoggableMixin, before=(NamedMixinMinimal, NamedMixin, NamedProtocol, HierarchicalMixinMinimal, HierarchicalMixin, HierarchicalProtocol))

    def __init__(self, *args, **kwargs):
        """
        Initialize the mixin and set up the logger.

        Args:
            *args: Additional positional arguments for superclasses.
            **kwargs: Additional keyword arguments for superclasses.
        """
        super(LoggableMixin, self).__init__(*args, **kwargs)

        # Start with no logger
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
        if not isinstance(self, type) and isinstance(self, NamedProtocol):
            return self.instance_name
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

    @override
    def __str__(self) -> str:
        """
        Get the string representation of the current object.

        Returns:
            str: The string representation.
        """
        if isinstance(self, NamedProtocol):
            return super().__str__()
        else:
            return f"{self.__class__.__name__}"