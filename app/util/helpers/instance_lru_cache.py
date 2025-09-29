# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools

from typing import TYPE_CHECKING, Concatenate, overload


if TYPE_CHECKING:
    from collections.abc import Callable


@overload
def instance_lru_cache[T: object, **P, R](wrapped: Callable[Concatenate[T, P], R], **lru_cache_kwargs) -> functools.cached_property: ...
@overload
def instance_lru_cache(**lru_cache_kwargs) -> Callable: ...


def instance_lru_cache[T: object, **P, R](wrapped: Callable[Concatenate[T, P], R] | None = None, **lru_cache_kwargs) -> Callable | functools.cached_property:
    if wrapped is None:
        return functools.partial(instance_lru_cache, **lru_cache_kwargs)

    @functools.wraps(wrapped)
    def wrapper(self: T) -> Callable[..., R]:
        return functools.lru_cache(**lru_cache_kwargs)(functools.update_wrapper(functools.partial(wrapped, self), wrapped))

    return functools.cached_property(wrapper)
