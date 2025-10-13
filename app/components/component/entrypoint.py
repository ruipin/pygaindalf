# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from collections.abc import Callable
from typing import Concatenate
from typing import cast as typing_cast

from .component import Component


# MARK: Component entrypoint decorator
type Entrypoint[T: Component, **P, R] = Callable[Concatenate[T, P], R]


def component_entrypoint[T: Component, **P, R](entrypoint: Entrypoint[T, P, R]) -> Entrypoint[T, P, R]:
    return typing_cast("T", Component).component_entrypoint_decorator(entrypoint)
