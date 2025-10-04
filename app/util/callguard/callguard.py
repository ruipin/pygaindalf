# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging
import sys

from typing import TYPE_CHECKING, ClassVar, Protocol, Unpack, runtime_checkable
from typing import cast as typing_cast

from . import lib
from .defines import CALLGUARD_TRACEBACK_HIDE, LOG
from .types import CallguardError, CallguardHandlerInfo


if TYPE_CHECKING:
    from .types import CallguardOptions, CallguardWrapped


# MARK: Callable decorator
def _is_same_class[T: object, **P, R](info: CallguardHandlerInfo[T, P, R]) -> bool:
    callee_type = type(info.callee_self) if not isinstance(info.callee_self, type) else info.callee_self
    caller_type = type(info.caller_self) if not isinstance(info.caller_self, type) else info.caller_self

    return caller_type is callee_type or issubclass(caller_type, callee_type) or issubclass(callee_type, caller_type)


def default_callguard_checker[T: object, **P, R](info: CallguardHandlerInfo[T, P, R]) -> bool:
    __tracebackhide__ = CALLGUARD_TRACEBACK_HIDE

    try:
        result = True

        if LOG.isEnabledFor(logging.DEBUG):
            caller_name = info.caller_frame.f_code.co_name
            LOG.debug(t"Caller frame: {caller_name} in {info.caller_module}")

            callee_name = info.method_name
            LOG.debug(t"Callee frame: {callee_name} in {info.callee_module}")

        if result and info.check_module:
            if info.caller_module != info.callee_module:
                LOG.error(t"Module mismatch: caller {info.caller_module}, callee {info.callee_module}")
                result = False

        if result and info.check_self:
            if info.caller_self is not info.callee_self:
                result = False

                if info.allow_same_class and _is_same_class(info):
                    result = True
                else:
                    LOG.error(t"Self mismatch: caller {info.caller_self}, callee {info.callee_self}")

        if not result and info.allow_same_module:
            if (info.caller_module == info.callee_module) or (
                (callee_self_module := getattr(info.callee_self, "__module__", None)) is not None and info.caller_module == callee_self_module
            ):
                result = True

        return result
    except Exception as e:
        logging.exception("Error in default_callguard_checker", exc_info=e)  # noqa: LOG015 as LOG might be disabled
        raise
    else:
        return result


class Callguard[T: object, **P, R]:
    _disabled: ClassVar[bool] = False

    @runtime_checkable
    class CallguardHandlerProtocol(Protocol):
        def __callguard_handler__(self: T, method: CallguardWrapped[T, P, R], info: CallguardHandlerInfo, /, *args: P.args, **kwargs: P.kwargs) -> R: ...

    def __init__(self, *, callee_module: str | None = None, **options: Unpack[CallguardOptions[T, P, R]]) -> None:
        self.options = options
        self.callee_module = callee_module

    def _get_method_name(self, method: CallguardWrapped[T, P, R], method_self: T, *args, **kwargs) -> str:
        method_name = self.options.get("method_name", getattr(method, "__name__", "<unknown>"))
        return typing_cast("str", method_name(method_self, *args, **kwargs)) if callable(method_name) else method_name

    @property
    def _frames_up(self) -> int:
        return self.options.get("frames_up", 0)

    @property
    def _check_module(self) -> bool:
        return self.options.get("check_module", False)

    @property
    def _allow_same_class(self) -> bool:
        return self.options.get("allow_same_class", True)

    @property
    def _allow_same_module(self) -> bool:
        return self.options.get("allow_same_module", True)

    @property
    def _guarded(self) -> bool:
        return not self._disabled and self.options.get("guard", True)

    def __call__(self, method: CallguardWrapped[T, P, R], method_self: T, *args, **kwargs) -> R:
        return self.guard(method, method_self, *args, **kwargs)

    def decorate(self, method: CallguardWrapped[T, P, R]) -> CallguardWrapped[T, P, R]:
        decorator = self.options.get("decorator")
        decorator_factory = self.options.get("decorator_factory")

        if decorator_factory is not None:
            if decorator is not None:
                msg = "Cannot specify both 'decorator' and 'decorator_factory'"
                raise ValueError(msg)
            decorator = decorator_factory(**self.options)

        if decorator is not None:
            method = decorator(method)

        return method

    def guard(self, method: CallguardWrapped[T, P, R], method_self: T, *args, **kwargs) -> R:
        __tracebackhide__ = CALLGUARD_TRACEBACK_HIDE

        if sys.is_finalizing() or not self._guarded:
            return method(method_self, *args, **kwargs)

        method_name = self._get_method_name(method, method_self, *args, **kwargs)
        LOG.debug(t"Callguard: Guarding call to {method_name}")

        callee_frame = lib.get_execution_frame(frames_up=self._frames_up)
        if callee_frame is None:
            msg = "No callee frame found"
            raise RuntimeError(msg)

        try:
            callee_module = self.callee_module
            if callee_module is None:
                callee_module = method.__module__
            if callee_module is None:
                msg = "No callee module found"
                raise RuntimeError(msg)

            caller_frame = callee_frame
            try:
                while True:
                    caller_frame = caller_frame.f_back
                    if caller_frame is None:
                        msg = "No caller frame found"
                        raise RuntimeError(msg)

                    caller_module = lib.get_execution_frame_module(caller_frame)
                    if caller_module is None:
                        msg = "No caller module found"
                        raise RuntimeError(msg)

                    if not caller_module.startswith("app.util.callguard"):
                        break

                info: CallguardHandlerInfo[T, P, R] = CallguardHandlerInfo(
                    method_name=method_name,
                    check_module=self._check_module,
                    check_self=True,
                    allow_same_class=self._allow_same_class,
                    allow_same_module=self._allow_same_module,
                    caller_frame=caller_frame,
                    callee_frame=callee_frame,
                    caller_self=lib.get_execution_frame_self(caller_frame),
                    callee_self=method_self,
                    caller_module=caller_module,
                    callee_module=callee_module,
                    default_checker=default_callguard_checker,
                    exception_class=CallguardError,
                )

                try:
                    if isinstance(method_self, Callguard[T, P, R].CallguardHandlerProtocol):
                        return method_self.__callguard_handler__(method, info, *args, **kwargs)
                    else:
                        if not info.default_checker(info):
                            msg = f"Callguard: Unauthorized call to {info.callee_module}.{info.method_name} of instance {info.callee_self}, from {info.caller_module}.{info.caller_frame.f_code.co_qualname} of instance {info.caller_self}"
                            raise info.exception_class(msg)
                        return method(method_self, *args, **kwargs)
                finally:
                    del info
            finally:
                if caller_frame is not None:
                    del caller_frame
        finally:
            if callee_frame is not None:
                del callee_frame
