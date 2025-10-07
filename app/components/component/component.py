# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools

from abc import ABCMeta
from collections.abc import Callable
from typing import (
    TYPE_CHECKING,
    Concatenate,
    Self,
    Unpack,
)

from ...util.callguard import CallguardOptions, CallguardWrapped, callguard_class
from ...util.helpers.decimal import DecimalFactory
from .component_config import BaseComponentConfig
from .component_meta import ComponentMeta


if TYPE_CHECKING:
    from .entrypoint import Entrypoint


# MARK: Component Base Class
@callguard_class(
    decorate_public_methods=True,
    ignore_patterns=("inside_entrypoint"),
)
class BaseComponent[C: BaseComponentConfig](ComponentMeta[C], metaclass=ABCMeta):
    # Decimal factory for precise calculations
    decimal: DecimalFactory

    def __init__(self, config: C, *args, **kwargs) -> None:
        super().__init__(config, *args, **kwargs)
        self._inside_entrypoint = False

        self.decimal = DecimalFactory(self.config.decimal)

    @classmethod
    def component_entrypoint_decorator[**P, R](cls, entrypoint: Entrypoint[Self, P, R]) -> Entrypoint[Self, P, R]:
        entrypoint.__dict__["__component_entrypoint__"] = True
        return entrypoint

    @classmethod
    def _handle_entrypoint[**P, R](cls, entrypoint: Entrypoint[Self, P, R], self: Self, /, *args: P.args, **kwargs: P.kwargs) -> R:
        # If we are already inside an entrypoint, call it directly
        if self.inside_entrypoint:
            return entrypoint(self, *args, **kwargs)

        # Execute entrypoint
        try:
            self._inside_entrypoint = True

            self._before_entrypoint(entrypoint.__name__, *args, **kwargs)

            try:
                result = self._wrap_entrypoint(entrypoint, *args, **kwargs)
            finally:
                self._after_entrypoint(entrypoint.__name__)

        finally:
            self._inside_entrypoint = False

        return result

    @classmethod
    def __callguard_decorator__[**P, R](
        cls, method: CallguardWrapped[Self, P, R], **options: Unpack[CallguardOptions[Self, P, R]]
    ) -> CallguardWrapped[Self, P, R]:
        @functools.wraps(method)
        def _wrapper(self: Self, *args: P.args, **kwargs: P.kwargs) -> R:
            # When inside an entrypoint all calls are allowed
            if self.inside_entrypoint:
                return method(self, *args, **kwargs)

            # Fail if this is not an entrypoint
            elif not method.__dict__.get("__component_entrypoint__", False):
                msg = f"Method '{options.get('method_name', method.__name__)}' is not a component entrypoint. It must be called through a component entrypoint method."
                raise RuntimeError(msg)

            return cls._handle_entrypoint(method, self, *args, **kwargs)

        return _wrapper

    @property
    def inside_entrypoint(self) -> bool:
        """Returns True if the component is currently inside an entrypoint method.

        This is used to prevent recursive calls to entrypoint methods.
        """
        return getattr(self, "_inside_entrypoint", False)

    def _assert_inside_entrypoint(self, msg: str = "") -> None:
        """Assert that the component is inside an entrypoint method.

        Raises a RuntimeError if not.
        """
        if not self.inside_entrypoint:
            if msg:
                msg = f" {msg}"
            msg = f"An entrypoint for {self.instance_name} is not being executed.{msg}"
            raise RuntimeError(msg)

    def _assert_outside_entrypoint(self, msg: str = "") -> None:
        """Assert that the component is outside an entrypoint method.

        Raises a RuntimeError if not.
        """
        if self.inside_entrypoint:
            if msg:
                msg = f" {msg}"
            msg = f"An entrypoint for '{self.instance_name}' is already being executed.{msg}"
            raise RuntimeError(msg)

    def _before_entrypoint(self, entrypoint_name: str, *args, **kwargs) -> None:
        self._assert_inside_entrypoint("Must not call '_before_entrypoint' outside an entrypoint method.")

        self.log.debug(t"Entering entrypoint '{entrypoint_name}'...")

    def _wrap_entrypoint[S: BaseComponent, **P, T](self: S, entrypoint: Callable[Concatenate[S, P], T], *args: P.args, **kwargs: P.kwargs) -> T:
        self._assert_inside_entrypoint("Must not call '_wrap_entrypoint' outside an entrypoint method.")

        with self.decimal.context_manager():
            return entrypoint(self, *args, **kwargs)

    def _after_entrypoint(self, entrypoint_name: str) -> None:
        self._assert_inside_entrypoint("Must not call '_after_entrypoint' outside an entrypoint method.")

        self.log.debug(t"Exiting entrypoint '{entrypoint_name}'.")
