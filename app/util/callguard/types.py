# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import dataclasses
import re

from types import FrameType
from typing import Iterable, Concatenate, TypedDict, NotRequired, Unpack, Protocol, Any
from collections.abc import Callable


# MARK: Wrapped Types
type CallguardWrapped[T : object, **P, R] = Callable[Concatenate[T,P], R]
type CallguardWrappedDecorator[T : object, **P, R] = Callable[[CallguardWrapped[T,P,R]], CallguardWrapped[T,P,R]]

class CallguardWrappedDecoratorFactory[T : object, **P, R](Protocol):
    @classmethod
    def __call__(cls, **options : 'Unpack[CallguardOptions]') -> CallguardWrappedDecorator[T,P,R]: ...


# MARK: Filter
class CallguardFilterInfo[T : object](TypedDict):
    klass     : type[T]
    attribute : str
    value     : Any
    guard     : bool
    decorate  : bool

class CallguardFilterMethod[T : object](Protocol):
    @classmethod
    def __call__(cls, **info : Unpack[CallguardFilterInfo[T]]) -> bool: ...


# MARK: Handler
@dataclasses.dataclass(slots=True, frozen=True)
class CallguardHandlerInfo[T : object, **P, R]:
    method_name : str
    check_module : bool
    check_self : bool
    allow_same_module : bool
    caller_frame : FrameType
    callee_frame : FrameType
    caller_self : object
    callee_self : object
    caller_module : str
    callee_module : str
    default_checker : 'Callable[[CallguardHandlerInfo], bool]'
    exception_class : type[Exception]



# MARK: Decorator Options
class CallguardOptions[T : object, **P, R](TypedDict):
    frames_up            : NotRequired[int]
    method_name          : NotRequired[str | Callable[Concatenate[T,P], str]]
    check_module         : NotRequired[bool]
    allow_same_module    : NotRequired[bool]
    guard                : NotRequired[bool]
    property_setter_only : NotRequired[bool]
    decorator            : NotRequired[CallguardWrappedDecorator[T,P,R] | None]
    decorator_factory    : NotRequired[CallguardWrappedDecoratorFactory[T,P,R] | None]

class CallguardGuardMethod[T : object, **P, R](Protocol):
    @classmethod
    def __call__(cls, method : T, **options : Unpack[CallguardOptions[T,P,R]]) -> T: ...


class CallguardClassOptions[T : object](TypedDict):
    ignore_patterns                : NotRequired[Iterable[str | re.Pattern[str]]]
    guard_private_methods          : NotRequired[bool]
    guard_public_methods           : NotRequired[bool]
    guard_skip_classmethods        : NotRequired[bool]
    guard_skip_instancemethods     : NotRequired[bool]
    guard_skip_properties          : NotRequired[bool]
    guard_ignore_patterns          : NotRequired[Iterable[str | re.Pattern[str]]]
    decorate_private_methods       : NotRequired[bool]
    decorate_public_methods        : NotRequired[bool]
    decorate_skip_classmethods     : NotRequired[bool]
    decorate_skip_instancemethods  : NotRequired[bool]
    decorate_skip_properties       : NotRequired[bool]
    decorate_ignore_patterns       : NotRequired[Iterable[str | re.Pattern[str]]]
    decorator                      : NotRequired[CallguardWrappedDecorator[T,...,Any]]
    decorator_factory              : NotRequired[CallguardWrappedDecoratorFactory[T,...,Any]]
    allow_same_module              : NotRequired[bool]



# MARK: Exception Classes
class CallguardError(RuntimeError):
    pass