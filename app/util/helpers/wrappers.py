# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools
from typing import Unpack, TypedDict, Callable, Concatenate, Any, override, overload, Self, NotRequired
from . import script_info
from collections.abc import Sequence


# MARK: Wrapper Property
type Wrapped[**P, R] = Callable[P, R]
type Wrapper[**P, R] = Callable[Concatenate[Wrapped[P,R], P], R]


# MARK: Wrapper Decorator
class WrapperDecorator[**P, R]:
    def __init__(self, wrapper : Wrapper[P,R]):
        self.wrapper = wrapper

    def __call__(self, method : Wrapped[P,R]) -> Wrapped[P,R]:
        return self.decorate(wrapped=method, wrapper=self.wrapper)

    @staticmethod
    def decorate(wrapped : Wrapped[P,R], wrapper : Wrapper[P,R]) -> Wrapped[P,R]:
        # Can't use functools.partial as it breaks instance binding for classes
        # TODO: In Python 3.14 this might change, try again
        #return functools.wraps(wrapped)(functools.partial(wrapper, wrapped))
        @functools.wraps(wrapped)
        def _wrapped(*args : P.args, **kwargs : P.kwargs) -> R:
            return wrapper(wrapped, *args, **kwargs)
        return _wrapped

def wrapper[**P, R](wrapper : Wrapper[P,R]) -> WrapperDecorator[P,R]:
    return WrapperDecorator(wrapper)


# MARK: Before Wrapper Decorator
# TODO: If WrapperDecorator starts relying on functools.partial, we should inherit from WrapperDecorator instead
type BeforeMethod[**P, R] = Callable[Concatenate[Wrapped[P,R],P], None]

class BeforeDecorator[**P, R]:
    def __init__(self, before : BeforeMethod[P,R]):
        self.before = before
    #   super().__init__(wrapper=functools.partial(self.before_wrapper, before))

    def __call__(self, method : Wrapped[P,R]) -> Wrapped[P,R]:
        return self.decorate(wrapped=method, before=self.before)

    @staticmethod
    def decorate(wrapped : Wrapped[P,R], before : BeforeMethod[P,R]) -> Wrapped[P,R]:
        @functools.wraps(wrapped)
        def _wrapped(*args : P.args, **kwargs : P.kwargs) -> R:
            before(wrapped, *args, **kwargs)
            return wrapped(*args, **kwargs)
        return _wrapped

def before[**P, R](before : BeforeMethod[P,R]) -> BeforeDecorator[P,R]:
    return BeforeDecorator(before)


# MARK: Before attribute check decorator
class BeforeAttributeCheckOptions[T : object, **P, R](TypedDict):
    attribute : str | Sequence[str]
    desired   : Any | Sequence[Any]
    message   : NotRequired[str | None]
    exception : NotRequired[type[Exception]]

class BeforeAttributeCheckDecorator[T : object, **P, R](BeforeDecorator[Concatenate[T,P],R]):
    def __init__(self, **options : Unpack[BeforeAttributeCheckOptions[T,P,R]]):
        self.options = options
        method : BeforeMethod[Concatenate[T,P],R] = self.before_attribute_check
        super().__init__(before=method)

    def before_attribute_check(self, wrapped : Wrapped[Concatenate[T,P],R], /, __p0 : T, *args : P.args, **kwargs : P.kwargs) -> None:
        target = __p0 # We use __p0 to make pyright happy above
        attr = self.options.get('attribute')
        desired = self.options.get('desired')
        message = self.options.get('message', None)
        exception = self.options.get('exception', ValueError)

        if isinstance(attr, str):
            if getattr(target, attr, None) != desired:
                raise exception(f"{message or f"Attribute '{attr}' must be {desired}"} when calling {target.__class__.__name__}.{wrapped.__name__} on {target!s}")
        else:
            for a, d in zip(attr, desired):
                if getattr(target, a, None) != d:
                    raise exception(f"{message or f"Attribute '{a}' must be {d}"} when calling {target.__class__.__name__}.{wrapped.__name__} on {target!s}")


@overload
def before_attribute_check(*, attribute : str, desired : Any, message : str | None = None, exception : type[Exception] = ValueError) -> BeforeAttributeCheckDecorator: ...
@overload
def before_attribute_check(*, attribute : Sequence[str], desired : Sequence[Any], message : str | None = None, exception : type[Exception] = ValueError) -> BeforeAttributeCheckDecorator: ...

def before_attribute_check[T : object, **P, R](**options : Unpack[BeforeAttributeCheckOptions[T,P,R]]) -> BeforeAttributeCheckDecorator[T,P,R]:
    return BeforeAttributeCheckDecorator[T,P,R](**options)
