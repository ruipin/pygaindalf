# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools

from typing import TYPE_CHECKING, Protocol, Unpack, runtime_checkable

from . import lib
from .callguard import Callguard


if TYPE_CHECKING:
    from .types import CallguardHandlerInfo, CallguardOptions, CallguardWrapped


# MARK: Callable decorator
class CallguardCallableDecorator[T: object, **P, R]:
    @runtime_checkable
    class CallguardHandlerProtocol(Protocol):
        def __callguard_handler__(self: T, method: CallguardWrapped[T, P, R], info: CallguardHandlerInfo, /, *args: P.args, **kwargs: P.kwargs) -> R: ...

    def __init__(self, **options: Unpack[CallguardOptions[T, P, R]]) -> None:
        self.options = options

    def __call__(self, method: CallguardWrapped[T, P, R]) -> CallguardWrapped[T, P, R]:
        return self.guard(method, **self.options)

    @staticmethod
    def guard(method: CallguardWrapped[T, P, R], **callguard_options: Unpack[CallguardOptions[T, P, R]]) -> CallguardWrapped[T, P, R]:
        if not lib.callguard_enabled(method):
            return method

        callguard = Callguard(**callguard_options)
        method = callguard.decorate(method)

        if callguard_options.get("guard", True):
            method = functools.wraps(method)(functools.partial(callguard.guard, method))

        setattr(method, "__callguarded__", True)
        return method


def callguard_callable[T: object, **P, R](**callguard_options: Unpack[CallguardOptions[T, P, R]]) -> CallguardCallableDecorator[T, P, R]:
    return CallguardCallableDecorator(**callguard_options)
