# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import Any, Callable
from . import script_info


class ClassPropertyDescriptor[C = type, T = Any]:
    def __init__(self, fget: Callable[[C], T]):
        self.fget: Any = fget

    def __get__(self, obj: Any, cls: type|None = None) -> T:
        if script_info.is_documentation_build():
            return self.fget
        if cls is None:
            cls = type(obj)
        return self.fget.__get__(obj, cls)()

    def __set__(self, obj: Any, value: Any) -> None:
        raise AttributeError("Can't set classproperty descriptors")

    def __delete__(self, obj: Any) -> None:
        raise AttributeError("Can't delete classproperty descriptors")


def classproperty[C = type, T = Any](func : Callable[[C], T]) -> ClassPropertyDescriptor[C, T]:
    if not script_info.is_documentation_build():
        if not isinstance(func, (classmethod, staticmethod)):
            func = classmethod(func) # pyright: ignore
    return ClassPropertyDescriptor(func) # pyright: ignore