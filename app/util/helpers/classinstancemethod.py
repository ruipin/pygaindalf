# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools

from typing import Any, Callable, override


# NOTE: We extend property to piggyback on any code that handles property descriptors differently than other class variables
class ClassInstanceMethodDescriptor[T = Any](property):
    def __init__(self, method: Callable[..., T]):
        self.method: Any = method

    @override
    def __get__(self, obj: Any, cls: type | None = None) -> Callable[..., T]: # pyright: ignore[reportIncompatibleMethodOverride] as we know we are not compatible with property
        @functools.wraps(self.method)
        def _wrapper(*args, **kwargs):
            if obj is not None:
                return self.method(obj, *args, **kwargs)
            else:
                return self.method(cls, *args, **kwargs)
        return _wrapper

    @override
    def __set__(self, obj: Any, value: Any) -> None:
        raise AttributeError("Can't set classinstancemethod descriptor")

    @override
    def __delete__(self, obj: Any) -> None:
        raise AttributeError("Can't delete classinstancemethod descriptor")


def classinstancemethod[T = Any](func : Callable[..., T]) -> ClassInstanceMethodDescriptor[T]:
    return ClassInstanceMethodDescriptor(func) # pyright: ignore