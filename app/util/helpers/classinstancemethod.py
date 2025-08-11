# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools

from typing import Any, Callable


class ClassInstanceMethodDescriptor[T = Any]:
    def __init__(self, method: Callable[..., T]):
        self.method: Any = method

    def __get__(self, obj: Any, cls: type|None = None) -> Callable[..., T]:
        @functools.wraps(self.method)
        def _wrapper(*args, **kwargs):
            if obj is not None:
                return self.method(obj, *args, **kwargs)
            else:
                return self.method(cls, *args, **kwargs)
        return _wrapper


def classinstancemethod[T = Any](func : Callable[..., T]) -> ClassInstanceMethodDescriptor[T]:
    return ClassInstanceMethodDescriptor(func) # pyright: ignore