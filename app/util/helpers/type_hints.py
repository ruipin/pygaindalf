# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import annotationlib
import typing
import warnings

from frozendict import frozendict

from . import script_info
from .classproperty import cached_classproperty


if typing.TYPE_CHECKING:
    from .generics import GenericAlias


# MARK: Type aliases
#: Alias for all accepted forms of type hints.
type TypeHint = type | GenericAlias | typing.ForwardRef | typing.TypeAliasType | typing.Union  # pyright: ignore[reportInvalidTypeForm]

#: Alias for all forms of resolved types that our methods can return.
type ResolvedType = type | GenericAlias | typing.ForwardRef


# MARK: typing.get_type_hints wrapper
def _get_type_hints(obj: typing.Any, format: annotationlib.Format = annotationlib.Format.FORWARDREF) -> typing.Mapping[str, typing.Any]:  # noqa: A002
    return frozendict(typing.get_type_hints(obj, format=format))


# MARK: Type hint caching
@typing.runtime_checkable
class SupportsCachedTypeHints(typing.Protocol):
    @property
    def __cached_type_hints__(self) -> typing.Mapping[str, typing.Any]: ...


class CachedTypeHintsMixin:
    __cached_type_hints_format__ = annotationlib.Format.FORWARDREF

    @cached_classproperty
    def __cached_type_hints__(cls) -> typing.Mapping[str, typing.Any]:
        return _get_type_hints(cls, format=cls.__cached_type_hints_format__)


# MARK: get_type_hints
def get_type_hints(obj: typing.Any) -> typing.Mapping[str, typing.Any]:
    # Since __cached_type_hints__ is a classproperty, it will not be available during documentation builds
    if not script_info.is_documentation_build() and isinstance(obj, SupportsCachedTypeHints):
        return obj.__cached_type_hints__
    else:
        return _get_type_hints(obj)


# MARK: get_type_hint
def get_type_hint(obj: typing.Any, attr: str) -> typing.Any | None:
    hints = get_type_hints(obj)
    return hints.get(attr, None)


# MARK: Union utilities
def iterate_type_hints(
    hint: TypeHint,
    *,
    origin: bool = False,
) -> typing.Iterable[ResolvedType]:
    from .generics import get_origin

    if isinstance(hint, typing.TypeAliasType):
        if (evaluate_value := getattr(hint, "evaluate_value", None)) is not None:
            hint = annotationlib.call_evaluate_function(evaluate_value, format=annotationlib.Format.FORWARDREF)
        else:
            msg = f"Cannot iterate over unresolved TypeAlias {hint!r}"
            raise TypeError(msg)

    if isinstance(hint, typing.ForwardRef):
        warnings.warn(f"{hint!s} type hint iteration not implemented, returning as-is", category=UserWarning, stacklevel=2)
        return hint

    if not isinstance(hint, typing.Union):
        if origin:
            yield get_origin(hint, passthrough=True)
        else:
            yield hint
        return

    for arg in typing.get_args(hint):
        if isinstance(arg, typing.Union):
            yield from iterate_type_hints(arg, origin=origin)
        elif origin:
            yield get_origin(arg, passthrough=True)
        else:
            yield arg


# MARK: Type hint matching
def match_type_hint(
    typ: type | GenericAlias,
    hint: TypeHint,
) -> ResolvedType | None:
    from .generics import get_origin

    typ_origin = get_origin(typ, passthrough=True)
    assert isinstance(typ_origin, type), f"typ_origin must be a type, got {type(typ_origin).__name__}"

    if isinstance(hint, typing.ForwardRef):
        warnings.warn(f"{hint!s} type hint matching not implemented, returning as-is", category=UserWarning, stacklevel=2)
        return hint

    for arg in iterate_type_hints(hint):
        arg_origin = get_origin(arg, passthrough=True)
        if not isinstance(arg_origin, type):
            msg = f"arg_origin must be a type, got {type(arg_origin).__name__}"
            raise TypeError(msg)

        if issubclass(typ_origin, arg_origin):
            return arg

    return None


def validate_type_hint(typ: type, hint: type | GenericAlias | typing.ForwardRef) -> bool:
    return match_type_hint(typ, hint) is not None
