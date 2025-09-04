# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import pydantic

from typing import Unpack, TYPE_CHECKING, override

from ..helpers import mro

from .defines import *
from .types import *
from .lib import *
from .callable_decorator import callguard_callable
from .class_decorator import CallguardClassDecorator



# MARK: Pydantic
def callguarded_model_mixin(**options : Unpack[CallguardClassOptions]):
    guard = options.get('guard_private_methods', True)

    decorate = options.get('decorate_private_methods', False)
    decorator = options.get('decorator', None) if decorate else None
    decorator_factory = options.get('decorator_factory', None) if decorate else None

    allow_same_module = options.get('allow_same_module', False)

    if not guard and not decorate:
        raise ValueError("At least one of 'guard_private_methods' or 'decorate_private_methods' must be True")

    class CallguardedModelMixin:
        if CALLGUARD_ENABLED:
            def __init_subclass__(cls) -> None:
                if not issubclass(cls, pydantic.BaseModel):
                    raise TypeError("GuardedModel can only be used with Pydantic BaseModel subclasses")

                super().__init_subclass__()
                mro.ensure_mro_order(cls, CallguardedModelMixin, before=pydantic.BaseModel)

                if not getattr(cls, '__callguarded__', False):
                    CallguardClassDecorator.guard(cls, **options)

        if CALLGUARD_ENABLED and CALLGUARD_GETATTR_SETATTR_ENABLED:
            # __getattribute__
            @callguard_callable(frames_up=2, method_name=lambda self, name: name, decorator=decorator, decorator_factory=decorator_factory, allow_same_module=allow_same_module, guard=guard)
            def __super_getattribute(self, name : str) -> Any:
                return super().__getattribute__(name)

            if not TYPE_CHECKING:
                @override
                def __getattribute__(self, name: str) -> Any:
                    if name == '__class__':
                        return super().__getattribute__(name)

                    private_attributes = getattr(self.__class__, '__private_attributes__', None)
                    if private_attributes is None or name not in private_attributes:
                        return super().__getattribute__(name)
                    return self.__super_getattribute(name)

            # __setattr__
            @callguard_callable(frames_up=2, method_name=lambda self, name, value: name, decorator=decorator, decorator_factory=decorator_factory, allow_same_module=allow_same_module, guard=guard)
            def __super_setattr(self, name : str, value : Any) -> None:
                return super().__setattr__(name, value)

            if not TYPE_CHECKING:
                @override
                def __setattr__(self, name: str, value: Any) -> None:
                    private_attributes = getattr(self.__class__, '__private_attributes__', None)
                    if private_attributes is None or name not in private_attributes:
                        return super().__setattr__(name, value)
                    return self.__super_setattr(name, value)

    return CallguardedModelMixin

CallguardedModelMixin = callguarded_model_mixin()