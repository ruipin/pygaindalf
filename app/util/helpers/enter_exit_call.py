# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING, NamedTuple, Self


if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping


class EnterExitCallInfo(NamedTuple):
    mthd: Callable
    args: Iterable | None
    kwargs: Mapping | None


class EnterExitCall:
    """Context manager to call enter and exit methods with optional arguments.

    Useful for temporarily changing state (e.g., freezing/unfreezing) in a with-block.
    """

    def __init__(
        self,
        enter: EnterExitCallInfo | Callable,
        exit: EnterExitCallInfo | Callable,  # noqa: A002 as it matches the __exit__ method name
    ) -> None:
        """Initialize the EnterExitCall context manager."""
        self._enter = enter
        self._exit = exit

        self.enter()

    def enter(self) -> Self:
        """Call the enter method with provided arguments."""
        info = self._enter
        if callable(info):
            info()
        else:
            args = info.args or ()
            kwargs = info.kwargs or {}
            info.mthd(*args, **kwargs)
        return self

    def __enter__(self) -> Self:
        """Enter the context (calls enter method).

        Returns:
            EnterExitCall: The context manager instance.

        """
        return self.enter()

    def exit(self) -> None:
        """Call the exit method with provided arguments."""
        info = self._exit
        if callable(info):
            info()
        else:
            args = info.args or ()
            kwargs = info.kwargs or {}
            info.mthd(*args, **kwargs)

    def __exit__(self, _, __, ___) -> None:
        """Exit the context (calls exit method).

        Args:
            _ : Exception type (unused).
            __: Exception value (unused).
            ___: Exception traceback (unused).

        """
        self.exit()
