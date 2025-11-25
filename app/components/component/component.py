# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools

from abc import ABCMeta
from collections.abc import Callable
from contextvars import ContextVar
from typing import (
    TYPE_CHECKING,
    Concatenate,
    Self,
    Unpack,
)

from ...util.callguard import CallguardOptions, CallguardWrapped, callguard_class
from .component_config import ComponentConfig
from .component_meta import ComponentMeta


if TYPE_CHECKING:
    from ...context import Context
    from ...portfolio.models.portfolio import PortfolioProtocol
    from ...util.helpers.decimal import DecimalFactory
    from .entrypoint import Entrypoint


# MARK: Current entrypoint context
CURRENT_COMPONENT: ContextVar[Component | None] = ContextVar("CURRENT_COMPONENT", default=None)

# MARK: Local configuration
HIDE_TRACEBACK = True


# MARK: Component Base Class
@callguard_class(
    decorate_public_methods=True,
    ignore_patterns=("inside_entrypoint"),
)
class Component[C: ComponentConfig](ComponentMeta[C], metaclass=ABCMeta):
    # MARK: Construction
    @staticmethod
    def get_current() -> Component | None:
        """Get the current component being executed in an entrypoint, if any."""
        return CURRENT_COMPONENT.get()

    def __init__(self, config: C, *args, **kwargs) -> None:
        super().__init__(config, *args, **kwargs)
        self._inside_entrypoint = False

    # MARK: Entrypoints
    @classmethod
    def _handle_entrypoint[**P, R](cls, entrypoint: Entrypoint[Self, P, R], self: Self, /, *args: P.args, **kwargs: P.kwargs) -> R:
        __tracebackhide__ = HIDE_TRACEBACK

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
    def component_entrypoint_decorator[**P, R](cls, entrypoint: Entrypoint[Self, P, R]) -> Entrypoint[Self, P, R]:
        entrypoint.__dict__["__component_entrypoint__"] = True
        return entrypoint

    @classmethod
    def __callguard_decorator__[**P, R](
        cls, method: CallguardWrapped[Self, P, R], **options: Unpack[CallguardOptions[Self, P, R]]
    ) -> CallguardWrapped[Self, P, R]:
        @functools.wraps(method)
        def _wrapper(self: Self, *args: P.args, **kwargs: P.kwargs) -> R:
            __tracebackhide__ = HIDE_TRACEBACK

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

    def _before_entrypoint(self, entrypoint_name: str, *args, **kwargs) -> None:  # noqa: ARG002
        self._assert_inside_entrypoint("Must not call '_before_entrypoint' outside an entrypoint method.")
        __tracebackhide__ = HIDE_TRACEBACK

        # self.log.debug(t"Entering entrypoint '{entrypoint_name}'...") # noqa: ERA001
        self._ctx_token = CURRENT_COMPONENT.set(self)

    def _wrap_entrypoint[S: Component, **P, T](self: S, entrypoint: Callable[Concatenate[S, P], T], *args: P.args, **kwargs: P.kwargs) -> T:
        self._assert_inside_entrypoint("Must not call '_wrap_entrypoint' outside an entrypoint method.")
        __tracebackhide__ = HIDE_TRACEBACK

        assert self.get_current() is self, "The current component does not match the executing component."
        return entrypoint(self, *args, **kwargs)

    def _after_entrypoint(self, entrypoint_name: str) -> None:  # noqa: ARG002
        self._assert_inside_entrypoint("Must not call '_after_entrypoint' outside an entrypoint method.")
        __tracebackhide__ = HIDE_TRACEBACK

        # self.log.debug(t"Exiting entrypoint '{entrypoint_name}'.") # noqa: ERA001
        CURRENT_COMPONENT.reset(self._ctx_token)

    # MARK: Context helpers
    @property
    def context_or_none(self) -> Context | None:
        if (context := self.__dict__.get("context", None)) is not None:
            return context

        from ...context import Context

        return Context.get_current_or_none()

    @property
    def context(self) -> Context:
        if (context := self.context_or_none) is None:
            msg = f"No active Context found for component '{self.instance_name}'. Please ensure you are inside a component entrypoint."
            raise RuntimeError(msg)
        return context

    @property
    def decimal(self) -> DecimalFactory:
        if (decimal := self.__dict__.get("decimal", None)) is not None:
            return decimal

        return self.context.decimal

    @property
    def portfolio(self) -> PortfolioProtocol:
        return self.context.portfolio
