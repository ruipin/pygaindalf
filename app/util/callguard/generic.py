# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from collections.abc import Callable
from typing import TYPE_CHECKING, Unpack, overload

from .callable_decorator import CallguardCallableDecorator
from .class_decorator import CallguardClassDecorator
from .classmethod_decorator import CallguardClassmethodDecorator
from .property_decorator import CallguardPropertyDecorator


if TYPE_CHECKING:
    from .types import CallguardClassOptions, CallguardOptions


# MARK: Generic Decorator
@overload
def callguard[T: property](obj: T, **callguard_options: Unpack[CallguardOptions]) -> T: ...


@overload
def callguard[T: classmethod](obj: T, **callguard_options: Unpack[CallguardOptions]) -> T: ...


@overload
def callguard[T: type](obj: T, **callguard_options: Unpack[CallguardClassOptions]) -> T: ...


@overload
def callguard[T: Callable](obj: T, **callguard_options: Unpack[CallguardOptions]) -> T: ...


def callguard[T](obj: T, **callguard_options) -> T:
    if isinstance(obj, staticmethod):
        msg = "callguard cannot be applied to staticmethods, as they have no self/cls"
        raise TypeError(msg)
    if isinstance(obj, property):
        return CallguardPropertyDecorator.guard(obj, **callguard_options)
    elif isinstance(obj, classmethod):
        return CallguardClassmethodDecorator.guard(obj, **callguard_options)
    elif isinstance(obj, type):
        return CallguardClassDecorator.guard(obj, **callguard_options)
    elif callable(obj):
        return CallguardCallableDecorator.guard(obj, **callguard_options)
    else:
        msg = "callguard can only be applied to classes, methods, or properties"
        raise TypeError(msg)
