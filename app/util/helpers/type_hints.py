# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import typing
import warnings
from frozendict import frozendict

from .classproperty import cached_classproperty

if typing.TYPE_CHECKING:
    from .generics import GenericAlias


# MARK: Type hint caching
@typing.runtime_checkable
class SupportsCachedTypeHints(typing.Protocol):
    @property
    def __cached_type_hints__(self) -> typing.Mapping[str, typing.Any]: ...


class CachedTypeHintsMixin:
    @cached_classproperty
    def __cached_type_hints__(cls) -> typing.Mapping[str, typing.Any]:
        return frozendict(typing.get_type_hints(cls))



# MARK: get_type_hints
def get_type_hints(obj : typing.Any) -> typing.Mapping[str, typing.Any]:
    if isinstance(obj, SupportsCachedTypeHints):
        return obj.__cached_type_hints__
    else:
        return typing.get_type_hints(obj)



# MARK: Union utilities
def iterate_type_hints[T](hint : GenericAlias, *, origin : bool = False) -> typing.Iterable[type | GenericAlias | typing.ForwardRef]:
    from .generics import get_origin

    if not isinstance(hint, typing.Union):
        if origin:
            yield get_origin(hint, passthrough=True)
        else:
            yield hint
        return

    for arg in typing.get_args(hint):
        if isinstance(arg, typing.Union):
            yield from iterate_type_hints(arg, origin=origin)
        else:
            if origin:
                yield get_origin(arg, passthrough=True)
            else:
                yield arg




# MARK: Type hint matching
def match_type_hint(typ : type | GenericAlias, hint : type | GenericAlias | typing.ForwardRef) -> type | GenericAlias | None:
    from .generics import get_origin

    typ_origin = get_origin(typ, passthrough=True)
    assert isinstance(typ_origin, type), f"typ_origin must be a type, got {typ_origin!r}"

    if isinstance(hint, typing.ForwardRef):
        warnings.warn(f"{hint!s} type hint matching not implemented, returning as-is", category=UserWarning, stacklevel=2)
        return hint

    for arg in iterate_type_hints(hint):
        arg_origin = get_origin(arg, passthrough=True)
        if not isinstance(arg_origin, type):
            return None

        if issubclass(typ_origin, arg_origin):
            return arg
        else:
            return None

    return None




def validate_type_hint(typ : type, hint : type | GenericAlias | typing.ForwardRef) -> bool:
    return match_type_hint(typ, hint) is not None