# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import Any, Callable, override
from . import script_info


# NOTE: We extend property to piggyback on any code that handles property descriptors differently than other class variables
class ClassPropertyDescriptor[C : object, T : Any](property):
    def __init__(self, fget: Callable[[C], T]):
        self.getter: Any = fget

    @override
    def __get__(self, obj: Any, cls: type | None = None) -> T: # pyright: ignore[reportIncompatibleMethodOverride] as we know we are not compatible with property
        if script_info.is_documentation_build():
            return self.getter
        if cls is None:
            cls = type(obj)
        return self.getter.__get__(obj, cls)()

    @override
    def __set__(self, obj: Any, value: Any) -> None:
        raise AttributeError("Can't set classproperty descriptors")

    @override
    def __delete__(self, obj: Any) -> None:
        raise AttributeError("Can't delete classproperty descriptors")


def classproperty[C : object, T : Any](func : Callable[[C], T]) -> ClassPropertyDescriptor[C, T]:
    if not script_info.is_documentation_build():
        if not isinstance(func, (classmethod, staticmethod)):
            func = classmethod(func) # pyright: ignore
    return ClassPropertyDescriptor(func) # pyright: ignore