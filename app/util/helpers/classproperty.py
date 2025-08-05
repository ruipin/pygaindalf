# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import Any, Callable


class ClassPropertyDescriptor[C = type, T = Any]:
    def __init__(self, fget: Callable[[C], T]):
        self.fget: Any = fget

    def __get__(self, obj: Any, cls: type|None = None) -> T:
        if cls is None:
            cls = type(obj)
        #return self.fget.__get__(obj, cls)()
        return self.fget.__get__(obj, cls)()


def classproperty[C = type, T = Any](func : Callable[[C], T]) -> ClassPropertyDescriptor[C, T]:
    if not isinstance(func, (classmethod, staticmethod)):
        func = classmethod(func) # pyright: ignore
    return ClassPropertyDescriptor(func) # pyright: ignore