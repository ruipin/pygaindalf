# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Annotated

from pydantic import InstanceOf

from ..helpers.type_hints import iterate_type_hints
from .uid import AsUidSerializer


type Child[T] = T
type NonChild[T] = Annotated[T, InstanceOf, AsUidSerializer]


def is_child_type(tp: type) -> bool:
    return any(hint is Child for hint in iterate_type_hints(tp, origin=True))


def is_non_child_type(tp: type) -> bool:
    return any(hint is NonChild for hint in iterate_type_hints(tp, origin=True))
