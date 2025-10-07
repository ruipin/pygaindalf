# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from collections.abc import Callable
from typing import Concatenate
from typing import cast as typing_cast

from .component import BaseComponent


# MARK: Component entrypoint decorator
type Entrypoint[T: BaseComponent, **P, R] = Callable[Concatenate[T, P], R]


def component_entrypoint[T: BaseComponent, **P, R](entrypoint: Entrypoint[T, P, R]) -> Entrypoint[T, P, R]:
    return typing_cast("T", BaseComponent).component_entrypoint_decorator(entrypoint)
