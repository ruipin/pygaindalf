# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import TYPE_CHECKING, Any, override

from . import script_info


if TYPE_CHECKING:
    from collections.abc import Callable


# NOTE: We extend property to piggyback on any code that handles property descriptors differently than other class variables
class ClassPropertyDescriptor[C: object, T: Any](property):
    def __init__(self, fget: Callable[[C], T], *, cached: bool = False) -> None:
        self.getter: Any = fget
        self.cached = cached

    @override
    def __get__(self, obj: Any, cls: type | None = None) -> T:  # pyright: ignore[reportIncompatibleMethodOverride] as we know we are not compatible with property
        if script_info.is_documentation_build():
            return self.getter

        if cls is None:
            cls = type(obj)
        result = self.getter.__get__(obj, cls)()
        if self.cached:
            setattr(cls, self.getter.__name__, result)
        return result

    @override
    def __set__(self, obj: Any, value: Any) -> None:
        msg = "Can't set classproperty descriptors"
        raise AttributeError(msg)

    @override
    def __delete__(self, obj: Any) -> None:
        msg = "Can't delete classproperty descriptors"
        raise AttributeError(msg)


def classproperty[C: object, T: Any](func: Callable[[C], T], *, cached: bool = False) -> ClassPropertyDescriptor[C, T]:
    if not script_info.is_documentation_build():
        if not isinstance(func, (classmethod, staticmethod)):
            func = classmethod(func)  # pyright: ignore[reportAssignmentType, reportArgumentType]
    return ClassPropertyDescriptor(func, cached=cached)  # pyright: ignore[reportArgumentType]


def cached_classproperty[C: object, T: Any](func: Callable[[C], T]) -> ClassPropertyDescriptor[C, T]:
    return classproperty(func, cached=True)
