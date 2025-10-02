# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Concatenate, NotRequired, TypedDict, Unpack, overload


if TYPE_CHECKING:
    from collections.abc import Sequence


# MARK: Wrapper Property
type Wrapped[**P, R] = Callable[P, R]
type Wrapper[**P, R] = Callable[Concatenate[Wrapped[P, R], P], R]


# MARK: Wrapper Decorator
class WrapperDecorator[**P, R]:
    def __init__(self, wrapper: Wrapper[P, R]) -> None:
        self.wrapper = wrapper

    def __call__(self, method: Wrapped[P, R]) -> Wrapped[P, R]:
        return self.decorate(wrapped=method, wrapper=self.wrapper)

    @staticmethod
    def decorate(wrapped: Wrapped[P, R], wrapper: Wrapper[P, R]) -> Wrapped[P, R]:
        return functools.wraps(wrapped)(functools.partial(wrapper, wrapped))


def wrapper[**P, R](wrapper: Wrapper[P, R]) -> WrapperDecorator[P, R]:
    return WrapperDecorator(wrapper)


# MARK: Before Wrapper Decorator
# TODO: If WrapperDecorator starts relying on functools.partial, we should inherit from WrapperDecorator instead
type BeforeMethod[**P, R] = Callable[Concatenate[Wrapped[P, R], P], None]


class BeforeDecorator[**P, R](WrapperDecorator[P, R]):
    def __init__(self, before: BeforeMethod[P, R]) -> None:
        super().__init__(wrapper=functools.partial(self.before_wrapper, before))

    @staticmethod
    def before_wrapper(before: BeforeMethod[P, R], wrapped: Wrapped[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        before(wrapped, *args, **kwargs)
        return wrapped(*args, **kwargs)


def before[**P, R](before: BeforeMethod[P, R]) -> BeforeDecorator[P, R]:
    return BeforeDecorator(before)


# MARK: Before attribute check decorator
class BeforeAttributeCheckOptions[T: object, **P, R](TypedDict):
    attribute: str | Sequence[str]
    desired: Any | Sequence[Any]
    message: NotRequired[str | None]
    exception: NotRequired[type[Exception]]


class BeforeAttributeCheckDecorator[T: object, **P, R](BeforeDecorator[Concatenate[T, P], R]):
    def __init__(self, **options: Unpack[BeforeAttributeCheckOptions[T, P, R]]) -> None:
        self.options = options
        method: BeforeMethod[Concatenate[T, P], R] = self.before_attribute_check
        super().__init__(before=method)

    def before_attribute_check(self, wrapped: Wrapped[Concatenate[T, P], R], /, __p0: T, *args: P.args, **kwargs: P.kwargs) -> None:
        target = __p0  # We use __p0 to make pyright happy above
        attr = self.options.get("attribute")
        desired = self.options.get("desired")
        message = self.options.get("message", None)
        exception = self.options.get("exception", ValueError)

        if isinstance(attr, str):
            if getattr(target, attr, None) != desired:
                try:
                    target_str = str(target)
                except:  # noqa: E722 as we really want to ensure we don't fail while building the exception message
                    target_str = "<str() raised exception>"
                msg = f"{message or f"Attribute '{attr}' must be {desired}"} when calling {type(target).__name__}.{wrapped.__name__} on {target_str}"
                raise exception(msg)
        else:
            for a, d in zip(attr, desired, strict=False):
                try:
                    target_str = str(target)
                except:  # noqa: E722 as we really want to ensure we don't fail while building the exception message
                    target_str = "<str() raised exception>"
                if getattr(target, a, None) != d:
                    msg = f"{message or f"Attribute '{a}' must be {d}"} when calling {type(target).__name__}.{wrapped.__name__} on {target_str}"
                    raise exception(msg)


@overload
def before_attribute_check(
    *, attribute: str, desired: Any, message: str | None = None, exception: type[Exception] = ValueError
) -> BeforeAttributeCheckDecorator: ...
@overload
def before_attribute_check(
    *, attribute: Sequence[str], desired: Sequence[Any], message: str | None = None, exception: type[Exception] = ValueError
) -> BeforeAttributeCheckDecorator: ...


def before_attribute_check[T: object, **P, R](**options: Unpack[BeforeAttributeCheckOptions[T, P, R]]) -> BeforeAttributeCheckDecorator[T, P, R]:
    return BeforeAttributeCheckDecorator[T, P, R](**options)


# MARK: After Wrapper Decorator
type AfterMethod[**P, R] = Callable[Concatenate[Wrapped[P, R], R, P], R]


class AfterDecorator[**P, R](WrapperDecorator[P, R]):
    def __init__(self, after: AfterMethod[P, R]) -> None:
        super().__init__(wrapper=functools.partial(self.after_wrapper, after))

    @staticmethod
    def after_wrapper(after: AfterMethod[P, R], wrapped: Wrapped[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        result = wrapped(*args, **kwargs)
        return after(wrapped, result, *args, **kwargs)


def after[**P, R](after: AfterMethod[P, R]) -> AfterDecorator[P, R]:
    return AfterDecorator(after)
