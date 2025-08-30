# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Protocol

from ....util.helpers.wrappers import before_attribute_check

stale_check = before_attribute_check('stale', False, "Stale check failed")

class StaleProtocol(Protocol):
    @property
    def stale(self) -> bool: ...