# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import Any


# MARK: No callguard Decorator
def no_callguard[T: Any](obj: T) -> T:
    setattr(obj, "__callguard_disabled__", True)
    return obj
