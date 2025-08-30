# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools
from typing import Unpack, TypedDict, Callable, Concatenate, Any, override, overload, Self
from . import script_info
from collections.abc import Sequence


# MARK: Wrapper Property
type Wrapped[**P, R] = Callable[P, R]
type Wrapper[**P, R] = Callable[Concatenate[Wrapped[P,R], P], R]

#class WrapperProperty[T : object, **P, R](property):
#    def __init__(self, wrapped : Wrapped[T,P,R], wrapper : Wrapper[T,P,R]):
#        self.wrapped = wrapped
#        self.wrapper = wrapper
#
#    @overload
#    def __get__(self, instance: None, owner: type[T], /) -> property: ...
#    @overload
#    def __get__(self, instance: T, owner: type[T] | None = None, /) -> BoundWrapped: ...
#
#    @override
#    def __get__(self, instance : T | None, owner : type[T] | None = None, /) -> property | BoundWrapped:
#        if instance is None:
#            return self
#        return functools.partial(self.wrapper, self.wrapped, instance)
#
#    @override
#    def __set__(self, obj: Any, value: Any) -> None:
#        raise AttributeError("Can't set classproperty descriptors")
#
#    @override
#    def __delete__(self, obj: Any) -> None:
#        raise AttributeError("Can't delete classproperty descriptors")


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
        #return functools.partial(wrapper, wrapped)
        #return functools.wraps(wrapped)(functools.partial(wrapper, wrapped))
        @functools.wraps(wrapped)
        def _wrapped(*args : P.args, **kwargs : P.kwargs) -> R:
            return wrapper(wrapped, *args, **kwargs)
        return _wrapped

def wrapper[**P, R](wrapper : Wrapper[P,R]) -> WrapperDecorator[P,R]:
    return WrapperDecorator(wrapper)


# MARK: Before Wrapper Decorator
type BeforeMethod[**P, R] = Callable[Concatenate[Wrapped[P,R],P], None]

class BeforeDecorator[**P, R](WrapperDecorator[P,R]):
    def __init__(self, before : BeforeMethod[P,R]):
        super().__init__(wrapper=functools.partial(self.before_wrapper, before))

    @staticmethod
    def before_wrapper(before : BeforeMethod[P,R], wrapped : Wrapped[P,R], *args : P.args, **kwargs : P.kwargs) -> R:
        before(wrapped, *args, **kwargs)
        return wrapped(*args, **kwargs)

def before[**P, R](before : BeforeMethod[P,R]) -> BeforeDecorator[P,R]:
    return BeforeDecorator(before)


# MARK: Before attribute check decorator
class BeforeAttributeCheckDecorator[T : object, **P, R](BeforeDecorator[Concatenate[T,P],R]):
    def __init__(self, attr : str | Sequence[str], desired : Any | Sequence[Any], message : str | None = None):
        # pyright is unhappy with functools.partial here
        #super().__init__(before=functools.partial(self.before_attribute_check, attr, desired, message))
        mthd : Callable[Concatenate[str, Any, str | None, Wrapped[Concatenate[T,P],R], T, P], None] = self.before_attribute_check
        @functools.wraps(mthd)
        def _wrapped(*args, **kwargs) -> None:
            return mthd(attr, desired, message, *args, **kwargs)
        super().__init__(before=_wrapped)

    @staticmethod
    def before_attribute_check(attr : str | Sequence[str], desired : Any | Sequence[Any], message : str | None, wrapped : Wrapped[Concatenate[T,P],R], self : T, *args : P.args, **kwargs : P.kwargs) -> None:
        if isinstance(attr, str):
            if getattr(self, attr, None) != desired:
                raise ValueError(f"{message or f"Attribute '{attr}' must be {desired}"} when calling {self.__class__.__name__}.{wrapped.__name__}")
        else:
            for a, d in zip(attr, desired):
                if getattr(self, a, None) != d:
                    raise ValueError(f"{message or f"Attribute '{a}' must be {d}"} when calling {self.__class__.__name__}.{wrapped.__name__}")


@overload
def before_attribute_check(attr : str, desired : Any, message : str | None = None) -> BeforeAttributeCheckDecorator: ...
@overload
def before_attribute_check(attr : Sequence[str], desired : Sequence[Any], message : str | None = None) -> BeforeAttributeCheckDecorator: ...

def before_attribute_check(attr : str | Sequence[str], desired : Any | Sequence[Any], message : str | None = None) -> BeforeAttributeCheckDecorator:
    return BeforeAttributeCheckDecorator(attr, desired, message)
