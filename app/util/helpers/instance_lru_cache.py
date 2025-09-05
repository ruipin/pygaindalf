# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools
from typing import Callable, Concatenate


def instance_lru_cache[T : object, **P, R](wrapped: Callable[Concatenate[T,P],R], **lru_cache_kwargs) -> functools.cached_property:

    @functools.wraps(wrapped)
    def wrapper(self : T) -> Callable[...,R]:
        return functools.lru_cache(**lru_cache_kwargs)(
            functools.update_wrapper(functools.partial(wrapped, self), wrapped)
        )

    return functools.cached_property(wrapper)