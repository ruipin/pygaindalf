# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Protocol, runtime_checkable

from ..helpers.wrappers import before_attribute_check


class SupersededError(ValueError):
    pass


@runtime_checkable
class SupersededProtocol(Protocol):
    @property
    def superseded(self) -> bool: ...


superseded_check = before_attribute_check(
    attribute="superseded",
    desired=False,
    message="Superseded check failed",
    exception=SupersededError,
)

reverted_check = before_attribute_check(
    attribute="reverted",
    desired=False,
    message="Destroyed check failed",
    exception=SupersededError,
)
