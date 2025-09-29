# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools
import logging
import sys

from typing import TYPE_CHECKING, ClassVar, Protocol, Unpack, runtime_checkable
from typing import cast as typing_cast

from . import lib
from .defines import LOG
from .types import CallguardError, CallguardHandlerInfo


if TYPE_CHECKING:
    from .types import CallguardOptions, CallguardWrapped


# MARK: Callable decorator
def default_callguard_checker[T: object, **P, R](info: CallguardHandlerInfo[T, P, R]) -> bool:
    try:
        result = True

        if LOG.isEnabledFor(logging.DEBUG):
            LOG.debug(t"Caller frame: {info.caller_frame.f_code.co_name} in {info.caller_module}")

            callee_name = info.callee_frame.f_locals.get("method_name", info.callee_frame.f_code.co_name)
            LOG.debug(t"Callee frame: {callee_name} in {info.callee_module}")

        if result and info.check_module:
            if info.caller_module != info.callee_module:
                LOG.error(t"Module mismatch: caller {info.caller_module}, callee {info.callee_module}")
                result = False

        if result and info.check_self:
            if info.caller_self is not info.callee_self:
                succeed = False

                if not info.allow_same_class:
                    msg = "Self mismatch and 'allow_same_class' is False"
                    raise ValueError(msg)  # noqa: TRY301

                if info.allow_same_class and not isinstance(info.caller_self, type) and not isinstance(info.callee_self, type):
                    caller_type = type(info.caller_self)
                    callee_type = type(info.callee_self)

                    if caller_type is callee_type or issubclass(caller_type, callee_type) or issubclass(callee_type, caller_type):
                        succeed = True

                if (
                    (not succeed)
                    and (not isinstance(info.callee_self, type) or not isinstance(info.caller_self, info.callee_self))
                    and (not isinstance(info.caller_self, type) or not isinstance(info.callee_self, info.caller_self))
                ):
                    LOG.error(t"Self mismatch: caller {info.caller_self}, callee {info.callee_self}")
                    result = False

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


class CallguardCallableDecorator[T: object, **P, R]:
    _disabled: ClassVar[bool] = False

    @runtime_checkable
    class CallguardHandlerProtocol(Protocol):
        def __callguard_handler__(self: T, method: CallguardWrapped[T, P, R], info: CallguardHandlerInfo, /, *args: P.args, **kwargs: P.kwargs) -> R: ...

    def __init__(self, **options: Unpack[CallguardOptions[T, P, R]]) -> None:
        self.options = options

    def __call__(self, method: CallguardWrapped[T, P, R]) -> CallguardWrapped[T, P, R]:
        return self.guard(method, **self.options)

    @staticmethod
    def guard(method: CallguardWrapped[T, P, R], **callguard_options: Unpack[CallguardOptions[T, P, R]]) -> CallguardWrapped[T, P, R]:  # noqa: PLR0915
        if not lib.callguard_enabled(method):
            return method

        decorator = callguard_options.get("decorator")
        decorator_factory = callguard_options.get("decorator_factory")

        if decorator_factory is not None:
            if decorator is not None:
                msg = "Cannot specify both 'decorator' and 'decorator_factory'"
                raise ValueError(msg)
            decorator = decorator_factory(**callguard_options)

        if decorator is not None:
            method = decorator(method)

        frames_up = callguard_options.get("frames_up", 1)
        check_module = callguard_options.get("check_module", False)
        allow_same_class = callguard_options.get("allow_same_class", True)
        allow_same_module = callguard_options.get("allow_same_module", True)
        method_name = callguard_options.get("method_name", getattr(method, "__name__", "<unknown>"))
        guard = callguard_options.get("guard", True)

        if guard:
            wrapped = method

            @functools.wraps(wrapped)
            def _callguard_wrapper(self: T, *args: P.args, **kwargs: P.kwargs) -> R:
                if CallguardCallableDecorator._disabled or sys.is_finalizing():
                    return wrapped(self, *args, **kwargs)

                _method_name = typing_cast("str", method_name(self, *args, **kwargs)) if callable(method_name) else method_name
                LOG.debug(t"Callguard: Guarding call to {_method_name}")

                callee_frame = lib.get_execution_frame(frames_up=frames_up)
                if callee_frame is None:
                    msg = "No callee frame found"
                    raise RuntimeError(msg)

                try:
                    callee_module = method.__module__
                    if callee_module is None:
                        msg = "No callee module found"
                        raise RuntimeError(msg)

                    caller_frame = callee_frame.f_back
                    if caller_frame is None:
                        msg = "No caller frame found"
                        raise RuntimeError(msg)

                    try:
                        caller_module = lib.get_execution_frame_module(caller_frame)
                        if caller_module is None:
                            msg = "No caller module found"
                            raise RuntimeError(msg)

                        info: CallguardHandlerInfo[T, P, R] = CallguardHandlerInfo(
                            method_name=_method_name,
                            check_module=check_module,
                            check_self=True,
                            allow_same_class=allow_same_class,
                            allow_same_module=allow_same_module,
                            caller_frame=caller_frame,
                            callee_frame=callee_frame,
                            caller_self=lib.get_execution_frame_self(caller_frame),
                            callee_self=self,
                            caller_module=caller_module,
                            callee_module=callee_module,
                            default_checker=default_callguard_checker,
                            exception_class=CallguardError,
                        )

                        try:
                            if isinstance(self, CallguardCallableDecorator[T, P, R].CallguardHandlerProtocol):
                                return self.__callguard_handler__(wrapped, info, *args, **kwargs)
                            else:
                                if not info.default_checker(info):
                                    msg = f"Callguard: Unauthorized call to {info.callee_module}.{info.method_name} of instance {info.callee_self}, from {info.caller_module}.{info.caller_frame.f_code.co_qualname} of instance {info.caller_self}"
                                    raise info.exception_class(msg)
                                return wrapped(self, *args, **kwargs)
                        finally:
                            del info
                    finally:
                        del caller_frame
                finally:
                    del callee_frame

            method = _callguard_wrapper

        setattr(method, "__callguarded__", True)
        return method


def callguard_callable[T: object, **P, R](**callguard_options: Unpack[CallguardOptions[T, P, R]]) -> CallguardCallableDecorator[T, P, R]:
    return CallguardCallableDecorator(**callguard_options)
