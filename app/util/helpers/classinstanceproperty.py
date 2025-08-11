# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Any, Callable


class ClassInstancePropertyDescriptor[C = type, T = Any]:
    """
    Descriptor for a read-only property accessible from both class and instances.
    The wrapped function receives either the instance (when accessed via instance)
    or the class (when accessed via class) as its first and only positional argument.
    """

    def __init__(self, fget: Callable[[C], T]):
        self.fget: Any = fget

    def __get__(self, obj: Any, cls: type | None = None) -> T:
        target = obj if obj is not None else cls
        return self.fget(target)

    def __set__(self, obj: Any, value: Any) -> None:
        raise AttributeError("Can't set classinstanceproperty descriptor")

    def __delete__(self, obj: Any) -> None:
        raise AttributeError("Can't delete classinstanceproperty descriptor")


def classinstanceproperty[C = type, T = Any](func: Callable[[C], T]) -> ClassInstancePropertyDescriptor[C, T]:
    return ClassInstancePropertyDescriptor(func)  # pyright: ignore
