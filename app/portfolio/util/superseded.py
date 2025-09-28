# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Protocol

from ...util.helpers.wrappers import before_attribute_check

class SupersededError(ValueError):
    pass

class SupersededProtocol(Protocol):
    @property
    def superseded(self) -> bool: ...

superseded_check = before_attribute_check(
    attribute='superseded',
    desired=False,
    message="Superseded check failed",
    exception=SupersededError
)