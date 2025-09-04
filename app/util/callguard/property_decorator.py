# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Unpack

from .defines import *
from .types import *
from .lib import *
from .callable_decorator import CallguardCallableDecorator


# MARK: Property Decorator
class CallguardPropertyDecorator[T : object, **P, R]:
    def __init__(self, **options : Unpack[CallguardOptions[T,P,R]]):
        self.options = options

    def __call__(self, prop : property) -> property:
        return self.guard(prop, **self.options)

    @staticmethod
    def guard(method : property, **callguard_options : Unpack[CallguardOptions[T,P,R]]) -> property:
        if not callguard_enabled(method):
            return method

        getter = method.fget
        setter = method.fset
        deleter = method.fdel

        orig_name = callguard_options.get('method_name', method.__name__)
        setter_only = callguard_options.get('property_setter_only', False)

        if setter_only:
            callguarded_getter = getter
        else:
            callguard_options['method_name'] = f"{orig_name}"
            callguarded_getter  = CallguardCallableDecorator.guard(getter, **callguard_options) if getter else None

        callguard_options['method_name'] = f"{orig_name}.setter"
        callguarded_setter = CallguardCallableDecorator.guard(setter, **callguard_options) if setter else None

        callguard_options['method_name'] = f"{orig_name}.deleter"
        callguarded_deleter = CallguardCallableDecorator.guard(deleter, **callguard_options) if deleter else None

        if callguarded_getter is getter and callguarded_setter is setter and callguarded_deleter is deleter:
            return method

        return property(
            callguarded_getter,
            callguarded_setter,
            callguarded_deleter,
            method.__doc__
        )

def callguard_property[T : object, **P, R](**callguard_options : Unpack[CallguardOptions[T,P,R]]) -> CallguardPropertyDecorator[T,P,R]:
    return CallguardPropertyDecorator(**callguard_options)